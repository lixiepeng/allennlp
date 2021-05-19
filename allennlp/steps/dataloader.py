import logging
import random
from math import floor, ceil
from typing import Optional, Iterator, Sequence

import more_itertools

from allennlp.common import Registrable
from allennlp.data import TensorDict, Instance, allennlp_collate, BatchSampler


class TangoDataLoader(Registrable):
    default_implementation = "batch_size"

    def num_batches_per_epoch(self) -> Optional[int]:
        """If the dataloader produces epochs of equal length, this is how you get the length."""
        raise NotImplementedError()

    def __iter__(self) -> Iterator[TensorDict]:
        raise NotImplementedError()

    def __len__(self) -> Optional[int]:
        logging.warning(
            "This function is deprecated because it's unclear which length you get back. Please call "
            "TangoDataLoader.num_batches_per_epoch() instead."
        )
        return self.num_batches_per_epoch()


@TangoDataLoader.register("batch_size")
class BatchSizeDataLoader(TangoDataLoader):
    def __init__(
        self,
        instances: Sequence[Instance],
        batch_size: int,
        drop_last: bool = False,
        shuffle: bool = True,
    ):
        self.instances = instances
        self.batch_size = batch_size
        self.drop_last = drop_last
        self.shuffle = shuffle

    def num_batches_per_epoch(self) -> Optional[int]:
        batch_count = len(self.instances) / self.batch_size
        if self.drop_last:
            return floor(batch_count)
        else:
            return ceil(batch_count)

    def __iter__(self) -> Iterator[TensorDict]:
        if self.shuffle:
            instances = list(
                self.instances
            )  # make a new list pointing to the same instance objects
            random.shuffle(instances)
        else:
            instances = self.instances

        for batch in more_itertools.chunked(instances, self.batch_size):
            if not self.drop_last or len(batch) >= self.batch_size:
                yield allennlp_collate(batch)


@TangoDataLoader.register("sampler")
class SamplerDataLoader(TangoDataLoader):
    def __init__(self, instances: Sequence[Instance], batch_sampler: BatchSampler):
        self.instances = instances
        self.batch_sampler = batch_sampler

    def num_batches_per_epoch(self) -> Optional[int]:
        return self.batch_sampler.get_num_batches(self.instances)

    def __iter__(self) -> Iterator[TensorDict]:
        for batch_indices in self.batch_sampler.get_batch_indices(self.instances):
            yield allennlp_collate([self.instances[i] for i in batch_indices])


@TangoDataLoader.register("batches_per_epoch")
class BatchesPerEpochDataLoader(TangoDataLoader):
    def __init__(self, inner: TangoDataLoader, batches_per_epoch: int):
        self.inner = inner
        self.iter = iter(inner)
        self.batches_per_epoch = batches_per_epoch

    def num_batches_per_epoch(self) -> Optional[int]:
        return self.batches_per_epoch

    def __iter__(self) -> Iterator[TensorDict]:
        batches_yielded = 0
        while batches_yielded < self.batches_per_epoch:
            try:
                yield next(self.iter)
                batches_yielded += 1
            except StopIteration:
                self.iter = iter(self.inner)


@TangoDataLoader.register("max_batches")
class MaxBatchesDataLoader(TangoDataLoader):
    def __init__(self, inner: TangoDataLoader, max_batches_per_epoch: int):
        self.inner = inner
        self.max_batches_per_epoch = max_batches_per_epoch

    def num_batches_per_epoch(self) -> Optional[int]:
        batches = self.inner.num_batches_per_epoch()
        if batches is None:
            return None
        else:
            return min(self.max_batches_per_epoch, batches)

    def __iter__(self) -> Iterator[TensorDict]:
        for i, batch in enumerate(iter(self.inner)):
            if i >= self.max_batches_per_epoch:
                return
            else:
                yield batch