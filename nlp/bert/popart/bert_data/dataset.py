# Copyright (c) 2019 Graphcore Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from itertools import chain


class DataSet(object):
    '''
    Converts an iterator that returns a list of np.ndarrays into an iterator that returns
    the same list with the ndarrays reshaped to match PopART's dataflow requirements.
    '''
    def __init__(self,
                 loader,
                 tensor_shapes,
                 device_iterations=1,
                 replication_factor=1,
                 accumulation_factor=1):
        self.tensor_shapes = tensor_shapes
        self.loader = loader
        self.device_iterations = device_iterations
        self.replication_factor = replication_factor
        self.accumulation_factor = accumulation_factor
        self.steps_per_epoch = len(loader)

        # Determine the shape of the batch based on samples_per_step, accumulation_factor and replication_factor
        self.outer_shapes = []

        # PopART expects inputs to be of the shape [device_iterations, accl_factor, repl_factor, micro_batch, *data_shape]
        if self.device_iterations > 1:
            self.outer_shapes += [self.device_iterations]

        if self.accumulation_factor > 1:
            self.outer_shapes += [self.accumulation_factor]

        if self.replication_factor > 1:
            self.outer_shapes += [self.replication_factor]

    def __iter__(self):
        self.loader_iterator = iter(self.loader)
        return self

    def __len__(self):
        return len(self.loader)

    def __next__(self):
        # Get the next sample/label
        items = next(self.loader_iterator)
        tensor_names = []

        # Reshape the input
        for i, id_shape in enumerate(self.tensor_shapes):
            tensor_names.append(id_shape[0])
            if id_shape[1] is not None:
                items[i] = items[i].reshape(
                    tuple(chain(self.outer_shapes, id_shape[1])))

        return dict(zip(tensor_names, items))
