from typing import Tuple, List, Dict, Callable

import torch
import numpy as np


class Compose:
    def __init__(self, transforms: List[Callable]):
        self.transforms = transforms

    def __call__(
        self,
        image: np.ndarray,
        targets: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        for t in self.transforms:
            inputs, targets = t(image, targets)

        return inputs, targets


class Resize:
    def __init__(self):
        raise NotImplementedError

    def __call__(
        self,
        image: np.ndarray,
        targets: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        raise NotImplementedError


class RandomFlip:
    def __init__(self, p: float = 0.2):
        self.p = p

    def __call__(
        self,
        image: np.ndarray,
        targets: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        h, _, _ = image.shape
        if np.random.random() < self.p:
            image = image[::-1, :]
            targets['masks'] = targets['masks'][:, ::-1, :]
            boxes = targets['boxes'].copy()
            targets['boxes'][:, 1::2] = h - boxes[:, 3::-2]

        return image, targets


class RandomRotation:
    def __init__(self, p: float = 0.2):
        self.p = p

    def __call__(
        self,
        image: np.ndarray,
        targets: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        if np.random.random() < self.p:
            old_height, old_width, _ = image.shape
            k = np.random.randint(4)
            image = np.rot90(image, k)

            if targets['boxes'] is not None:
                boxes = targets['boxes'].copy()
                for _ in range(k):
                    boxes = np.array([[
                        box[1], old_width - 1 - box[2],
                        box[3], old_width - 1 - box[0]] for box in boxes])

                    old_width, old_height = old_height, old_width

            if targets['masks'] is not None:
                targets['masks'] = np.array(
                    [np.rot90(mask, k) for mask in targets['masks']])

        return image, targets


class Pad:
    """
    Pads the image to the input width and height, filling the
    background with mean and putting the image in the top-left.
    Note: this expects im_w <= width and im_h <= height
    """
    def __init__(self, width, height, mean=None, p: float = 0.2):
        self.mean = mean
        self.width = width
        self.height = height

    def __call__(
        self,
        image: np.ndarray,
        targets: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        im_h, im_w, depth = image.shape

        expand_image = np.zeros(
            (self.height, self.width, depth),
            dtype=image.dtype)
        expand_image[:, :, :] = self.mean
        expand_image[:im_h, :im_w] = image
        if targets['boxes'] is not None:
            expand_boxes = np.zeros_like(targets['boxes'])
            targets['boxes'] = expand_boxes

        if targets['masks'] is not None:
            expand_masks = np.zeros(
                (targets['masks'].shape[0], self.height, self.width),
                dtype=targets['masks'].dtype)
            expand_masks[:, :im_h, :im_w] = targets['masks']
            targets['masks'] = expand_masks

        return expand_image, targets


class RandomSaturation:
    def __init__(self, lower=0.5, upper=1.5, p=0.2):
        self.lower = lower
        self.upper = upper
        assert self.upper >= self.lower, "contrast upper must be >= lower."
        assert self.lower >= 0, "contrast lower must be non-negative."

    def __call__(
        self,
        image: np.ndarray,
        targets: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        if random.randint(2):
            image[:, :, 1] *= random.uniform(self.lower, self.upper)

        return image, targets


class RandomHue:
    def __init__(self, delta=18.0):
        assert delta >= 0.0 and delta <= 360.0
        self.delta = delta

    def __call__(
        self,
        image: np.ndarray,
        targets: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        if np.random.randint(2):
            image[:, :, 0] += np.random.uniform(-self.delta, self.delta)
            image[:, :, 0][image[:, :, 0] > 360.0] -= 360.0
            image[:, :, 0][image[:, :, 0] < 0.0] += 360.0

        return image, targets


class RandomContrast:
    def __init__(self, lower=0.5, upper=1.5, p=0.2):
        self.lower = lower
        self.upper = upper
        self.p = p
        assert self.upper >= self.lower, "contrast upper must be >= lower."
        assert self.lower >= 0, "contrast lower must be non-negative."

    def __call__(
        self,
        image: np.ndarray,
        targets: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        if np.random.randint(2):
            alpha = np.random.uniform(self.lower, self.upper)
            image *= alpha

        return image, targets


class RandomBrightness:
    def __init__(self, delta=32):
        assert delta >= 0.0
        assert delta <= 255.0
        self.delta = delta

    def __call__(
        self,
        image: np.ndarray,
        targets: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        if np.random.randint(2):
            delta = np.random.uniform(-self.delta, self.delta)
            image += delta

        return image, targets


class ToTensor:
    def __call__(
        self,
        image: np.ndarray,
        targets: Dict[str, np.ndarray]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        return torch.from_numpy(image.astype(np.float32)).permute(2, 0, 1), targets