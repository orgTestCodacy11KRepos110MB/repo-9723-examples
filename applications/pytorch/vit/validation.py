# Copyright (c) 2021 Graphcore Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This file has been modified by Graphcore

import numpy as np
import poptorch
import torch
import transformers

from args import parse_args
from dataset import get_data
from ipu_options import get_options
from log import logger
from metrics import accuracy
from models import PipelinedViTForImageClassification, PipelinedViTForImageClassificationPretraining
from checkpoint import restore_checkpoint


if __name__ == "__main__":
    # Validation loop
    # Build config from args
    config = transformers.ViTConfig(**vars(parse_args()))
    logger.info(f"Running config: {config.config}")

    # Execution parameters
    opts = get_options(config)

    test_loader = get_data(config, opts, train=False, async_dataloader=True)

    # Init from a checkpoint
    if config.pretrain:
        model = PipelinedViTForImageClassificationPretraining(config).eval()
        model_state_dict = restore_checkpoint(config, val=True)
        model.load_state_dict(model_state_dict)
    else:
        model = PipelinedViTForImageClassification.from_pretrained(config.pretrained_checkpoint, config=config).parallelize().train()

    if config.precision.startswith("16."):
        model.half()

    valid_opts = poptorch.Options()
    valid_opts.deviceIterations(4)
    valid_opts.outputMode(poptorch.OutputMode.All)
    valid_opts.Precision.enableStochasticRounding(False)

    # Wrap in the PopTorch inference wrapper
    inference_model = poptorch.inferenceModel(model, options=valid_opts)
    all_preds, all_labels, all_losses = [], [], []
    for step, (input_data, labels) in enumerate(test_loader):
        losses, logits = inference_model(input_data, labels)
        preds = torch.argmax(logits, dim=-1)
        acc = accuracy(preds, labels)
        all_preds.append(preds.detach().clone())
        all_labels.append(labels.detach().clone())
        logger.info("Valid Loss: {:.3f} Acc: {:.3f}".format(torch.mean(losses).item(), acc))

    all_preds = torch.cat(all_preds)
    all_labels = torch.cat(all_labels)
    val_accuracy = accuracy(all_preds, all_labels)
    num_samples = all_preds.shape[0]

    logger.info("\n")
    logger.info("Validation Results")
    logger.info("Valid Accuracy: %2.5f" % val_accuracy)
    logger.info("Number of samples: %d" % num_samples)
