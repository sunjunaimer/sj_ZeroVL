import argparse
import os
import sys
import torch

from copy import deepcopy
try:
    from apex.parallel import convert_syncbn_model
except ImportError:
    pass

exec_path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
project_path = os.path.join(exec_path, '../../..')
sys.path.insert(0, project_path)

from zerovl.core import init_device
from zerovl.datasets import DATALOADER
from zerovl.models import PIPELINE
from zerovl.core import cfg, update_cfg
from zerovl.utils import build_from_cfg, ENV

from zerovl.tasks.clip.clip_runner import CLIPRunner
from zerovl.tasks.clip.clip_bsgs_runner import CLIP_BSGS_Runner
from zerovl.tasks.clip.config import task_cfg_init_fn, update_clip_config


def parse_args():
    # Parse args with argparse tool
    parser = argparse.ArgumentParser(description='ZeroVL training')
    parser.add_argument('--cfg', type=str, required=True,
                        help='experiment configure file name')
    parser.add_argument("--local_rank", type=int, default=0)  # Compatibility with torch launch.py
    args, cfg_overrided = parser.parse_known_args()

    # Update config from yaml and argv for override
    update_cfg(task_cfg_init_fn, args.cfg, cfg_overrided, preprocess_fn=update_clip_config)

    # Record the global config and its snapshot (for easy experiment reproduction)
    ENV.cfg = cfg
    ENV.cfg_snapshot = deepcopy(cfg)
    ENV.local_rank = args.local_rank



def main():
    # Configuration: user config updating and global config generating
    parse_args()

    # Initialization: set device, generate global config and inform the user library
    init_device(cfg)

    # Build model
    model = build_from_cfg(cfg.model.name, cfg, PIPELINE).to(ENV.device)

    if cfg.model.syncbn:
        if cfg.dist.name == 'torch':
            model = torch.nn.SyncBatchNorm.convert_sync_batchnorm(model)
        elif cfg.dist.name == 'apex':
            model = convert_syncbn_model(model)
        else:
            raise NotImplementedError
    
    # Context building: dataloader
    data_loaders = build_from_cfg(cfg.data.name, cfg, DATALOADER)


    # Runner: building and running
    if cfg.runner.name == 'clip_bsgs':
        runner = CLIP_BSGS_Runner(cfg, data_loaders, model)
    else:
        runner = CLIPRunner(cfg, data_loaders, model)
    runner.run()


if __name__ == '__main__':
    main()
