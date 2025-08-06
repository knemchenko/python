import os
import random
import numpy as np


def seed_everything(seed: int = 42):
    """
    Sets the random seed for reproducibility.

    Args:
        seed (int): The seed to use.
    """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)

    # Note: For full reproducibility with PyTorch, you would also need:
    # import torch
    # torch.manual_seed(seed)
    # torch.cuda.manual_seed(seed)
    # torch.backends.cudnn.deterministic = True
    # torch.backends.cudnn.benchmark = False
    # Since we cannot install torch, these are commented out.

    print(f"Global random seed set to {seed}")
