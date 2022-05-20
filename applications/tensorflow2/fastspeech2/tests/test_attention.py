# Copyright (c) 2021 Graphcore Ltd. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import pytest
import json
import yaml
import numpy as np
import tensorflow as tf
from tensorflow.python import ipu
from pathlib import Path


def setup_random_seed():
    seed = 1989
    np.random.seed(seed)
    tf.random.set_seed(seed)
    ipu.utils.reset_ipu_seed(seed)


def test_attention():
    from utils import create_ipu_config
    from fastspeech2 import Attention
    from fastspeech2 import FastSpeech2Config as IPUFastSpeech2Config
    from tests.test_utils import check_tensor
    from tests.tf2_fastspeech2 import TFFastSpeechAttention, FastSpeech2Config

    setup_random_seed()
    test_dir = Path(__file__).parent
    with open(Path(test_dir, "test_configs", "test.yaml"), "r") as f:
        conf1 = yaml.load(f, Loader=yaml.Loader)
    with open(Path(test_dir, "test_configs", "test.json"), "r") as f:
        conf2 = json.load(f)

    batch_size = conf2["batch_size"]
    seq_len = conf2["max_seq_length"]
    hidden_size = conf2["encoder_hidden_size"]
    inp = np.random.random((batch_size, seq_len, hidden_size))
    inputs = tf.convert_to_tensor(inp, tf.float32)
    attention_mask = tf.convert_to_tensor(
        [[1, 1, 1, 1, 1, 1, 1, 1, 1, 1]], tf.float32)

    gconf = FastSpeech2Config(**conf1["fastspeech2_params"])
    iconf = IPUFastSpeech2Config(**conf2)
    cfg = create_ipu_config(
        available_memory_proportion=conf2["available_memory_proportion"],
        num_required_ipus=1,
        partials_type=conf2["partials_type"],
        fp_exceptions=conf2["fp_exceptions"],
        enable_stochastic_rounding=conf2["stochastic_rounding"],
        num_io_tiles=0)

    model_gpu = TFFastSpeechAttention(gconf.encoder_self_attention_params)
    with tf.GradientTape() as tape:
        out_gpu = model_gpu([inputs, attention_mask])
        loss1 = tf.reduce_mean(tf.math.abs(out_gpu))

    strategy = ipu.ipu_strategy.IPUStrategy()
    with strategy.scope():
        model_ipu = Attention(iconf.encoder_self_attention_params)
        dummy_output = model_ipu([inputs, attention_mask])
        gw = model_gpu.get_weights()
        model_ipu.set_weights(gw)
        iw = model_ipu.get_weights()
        with tf.GradientTape() as tape2:
            out_ipu = model_ipu([inputs, attention_mask])

    for w1, w2 in zip(gw, iw):
        check_tensor(w1, w2)

    check_tensor(out_gpu[0].numpy(), out_ipu[0].numpy())
