# Copyright (c) 2021 Graphcore Ltd. All rights reserved.

import popdist
import popdist.tensorflow
from tensorflow.python.ipu import horovod as hvd
import random
import tensorflow as tf
import numpy as np
from tensorflow.python.ipu.utils import reset_ipu_seed
import typing


def set_host_seed(seed: typing.Optional[int]) -> typing.Optional[int]:
    if seed is None and popdist.isPopdistEnvSet():
        seed = int(hvd.broadcast(tf.convert_to_tensor(value=random.randint(0, 2**32 - 1), dtype=tf.int32), 0))

    if seed is not None:
        random.seed(seed)
        # Set other seeds to different values for extra safety.
        # The new seeds are defined indirectly by the main seed,
        # since they are generated by the seeded random function.
        tf.random.set_seed(random.randint(0, 2**32 - 1))
        np.random.seed(random.randint(0, 2**32 - 1))

    return seed


def set_ipu_seed(seed: typing.Optional[int]):
    if seed is not None:
        reset_ipu_seed(seed, experimental_identical_replicas=True)
