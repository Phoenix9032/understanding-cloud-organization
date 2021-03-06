from pathlib import Path
from typing import Any, List, Tuple
from types import ModuleType

import torch
import torch.nn as nn
import ttach as tta
from tqdm import tqdm

import uco.model.optimizer as module_optimizer
import uco.model.scheduler as module_scheduler
import uco.data_loader.augmentation as module_aug
import uco.data_loader.data_loaders as module_data
import uco.model.loss as module_loss
import uco.model.metric as module_metric
import uco.model.model as module_arch
from uco.trainer import Trainer
from uco.utils import setup_logger, setup_logging, seed_everything

from . import h5


class ManagerBase:
    def __init__(self, config: dict):
        setup_logging(config)
        seed_everything(config["seed"])
        self.logger = setup_logger(self, config["verbose"])
        self.cfg = config

    def get_instance(
        self, module: ModuleType, name: str, config: dict, *args: Any
    ) -> Any:
        """
        Helper to construct an instance of a class.

        Parameters
        ----------
        module : ModuleType
            Module containing the class to construct.
        name : str
            Name of class, as would be returned by ``.__class__.__name__``.
        config : dict
            Dictionary containing an 'args' item, which will be used as ``kwargs`` to
            construct the class instance.
        args : Any
            Positional arguments to be given before ``kwargs`` in ``config``.
        """
        ctor_name = config[name]["type"]
        self.logger.info(f"Building: {module.__name__}.{ctor_name}")
        return getattr(module, ctor_name)(*args, **config[name]["args"])

    def setup_device(
        self, model: nn.Module, target_devices: List[int]
    ) -> Tuple[torch.device, List[int]]:
        """
        setup GPU device if available, move model into configured device
        """
        available_devices = list(range(torch.cuda.device_count()))

        if not available_devices:
            self.logger.warning(
                "There's no GPU available on this machine. "
                "Training will be performed on CPU."
            )
            device = torch.device("cpu")
            model = model.to(device)
            return model, device

        if not target_devices:
            self.logger.info("No GPU selected. Training will be performed on CPU.")
            device = torch.device("cpu")
            model = model.to(device)
            return model, device

        max_target_gpu = max(target_devices)
        max_available_gpu = max(available_devices)

        if max_target_gpu > max_available_gpu:
            msg = (
                f"Configuration requests GPU #{max_target_gpu} but only  "
                f"{max_available_gpu} available. Check the configuration and try again."
            )
            self.logger.critical(msg)
            raise Exception(msg)

        self.logger.info(
            f"Using devices {target_devices} of available devices {available_devices}"
        )
        device = torch.device(f"cuda:{target_devices[0]}")
        if len(target_devices) > 1:
            model = nn.DataParallel(model, device_ids=target_devices)
        else:
            model = model.to(device)
        return model, device


class TrainingManager(ManagerBase):
    """
    Top level class to construct objects for training.
    """

    def run(self, resume: str) -> None:
        cfg = self.cfg.copy()

        model = self.get_instance(module_arch, "arch", cfg)
        model, device = self.setup_device(model, cfg["target_devices"])
        torch.backends.cudnn.benchmark = True  # disable if not consistent input sizes

        # param_groups = self.setup_param_groups_segmentation(model, cfg["optimizer"])
        param_groups = self.setup_param_groups_classifier(model, cfg["optimizer"])
        optimizer = self.get_instance(module_optimizer, "optimizer", cfg, param_groups)
        lr_scheduler = self.get_instance(
            module_scheduler, "lr_scheduler", cfg, optimizer
        )
        model, optimizer, start_epoch = self.resume_checkpoint(
            resume, model, optimizer, cfg
        )
        try:
            transforms = self.get_instance(module_aug, "augmentation", cfg)
        except:
            cfg["augmentation"]["type"] = "LightTransforms"
            transforms = self.get_instance(module_aug, "augmentation", cfg)

        data_loader = self.get_instance(module_data, "data_loader", cfg, transforms)
        valid_data_loader = data_loader.split_validation()

        self.logger.info("Getting loss and metric function handles")
        loss = self.get_instance(module_loss, "loss", cfg).to(device)
        metrics = [getattr(module_metric, met) for met in cfg["metrics"]]

        self.logger.info("Initialising trainer")
        trainer = Trainer(
            model,
            loss,
            metrics,
            optimizer,
            start_epoch=start_epoch,
            config=cfg,
            device=device,
            data_loader=data_loader,
            valid_data_loader=valid_data_loader,
            lr_scheduler=lr_scheduler,
        )

        checkpoint_dir = trainer.train()
        self.logger.info("Training completed.")
        return checkpoint_dir

    def setup_param_groups_segmentation(self, model: nn.Module, config: dict) -> dict:
        """
        Helper to apply options to param groups.
        """
        encoder_opts = config["encoder"]
        decoder_opts = config["decoder"]

        encoder_weight_params = []
        encoder_bias_params = []
        decoder_weight_params = []
        decoder_bias_params = []

        for name, param in model.encoder.named_parameters():
            if name.endswith("bias"):
                encoder_bias_params.append(param)
            else:
                encoder_weight_params.append(param)

        for name, param in model.decoder.named_parameters():
            if name.endswith("bias"):
                decoder_bias_params.append(param)
            else:
                decoder_weight_params.append(param)

        self.logger.info(f"Found {len(encoder_weight_params)} encoder weight params")
        self.logger.info(f"Found {len(encoder_bias_params)} encoder bias params")
        self.logger.info(f"Found {len(decoder_weight_params)} decoder weight params")
        self.logger.info(f"Found {len(decoder_bias_params)} decoder bias params")

        params = [
            {"params": encoder_weight_params, **encoder_opts},
            {"params": decoder_weight_params, **decoder_opts},
            {"params": encoder_bias_params, **encoder_opts},
            {"params": decoder_bias_params, **decoder_opts},
        ]
        return params

    def setup_param_groups_classifier(self, model: nn.Module, config: dict) -> dict:
        """
        Helper to apply options to param groups.
        """
        weight_params = []
        bias_params = []

        for name, param in model.named_parameters():
            if name.endswith("bias"):
                bias_params.append(param)
            else:
                weight_params.append(param)

        self.logger.info(f"Found {len(weight_params)} weight params")
        self.logger.info(f"Found {len(bias_params)} bias params")

        params = [
            {"params": weight_params, **config["args"]},
            {"params": bias_params, **config["args"]},
        ]
        return params

    def resume_checkpoint(self, resume_path, model, optimizer, config):
        """
        Resume from saved checkpoint.
        """
        if not resume_path:
            return model, optimizer, 0

        self.logger.info(f"Loading checkpoint: {resume_path}")
        checkpoint = torch.load(resume_path)
        model.load_state_dict(checkpoint["state_dict"])

        # load optimizer state from checkpoint only when optimizer type is not changed.
        if checkpoint["config"]["optimizer"]["type"] != config["optimizer"]["type"]:
            self.logger.warning(
                "Warning: Optimizer type given in config file is different from "
                "that of checkpoint. Optimizer parameters not being resumed."
            )
        else:
            optimizer.load_state_dict(checkpoint["optimizer"])

        self.logger.info(f'Checkpoint "{resume_path}" loaded')
        return model, optimizer, checkpoint["epoch"]


class InferenceManager(ManagerBase):
    """
    Top level class to perform inference.
    """

    def run(self, model_checkpoint: str) -> None:
        cfg = self.cfg.copy()
        device = self.setup_device(cfg["device"])
        torch.cuda.set_device(device)
        checkpoint = self.load_checkpoint(model_checkpoint, device)
        best_score = self.check_score(checkpoint)
        train_cfg = checkpoint["config"]

        model = self.get_instance(module_arch, "arch", train_cfg)
        model.load_state_dict(checkpoint["state_dict"])
        torch.backends.cudnn.benchmark = True  # disable if not consistent input sizes

        tta_model = self.build_tta_model(model, cfg, device)
        transforms = self.get_instance(module_aug, "augmentation", train_cfg)
        data_loader = self.get_instance(module_data, "data_loader", cfg, transforms)
        writer = self.build_h5_writer(cfg, train_cfg, model_checkpoint, best_score)

        self.logger.info("Performing inference")
        tta_model.eval()
        with torch.no_grad():
            for bidx, (f, data) in tqdm(enumerate(data_loader), total=len(data_loader)):
                data = data.to(device)
                output = torch.sigmoid(tta_model(data))
                output = output.cpu().numpy()
                writer.write(output)

        self.logger.info(writer.close())

    # -- helpers ---------------------------------------------------------------------

    def build_tta_model(self, model, config, device):
        tta_model = getattr(tta, config["tta"])(
            model,
            tta.Compose([tta.HorizontalFlip(), tta.VerticalFlip()]),
            merge_mode="mean",
        )
        tta_model.to(device)
        return tta_model

    def build_h5_writer(self, config, train_cfg, model_checkpoint, score):
        group_name = self.get_group_name_for_config(train_cfg)
        writer = getattr(h5, config["write"])(
            filename=config["output"]["raw"],
            group_name=group_name,
            dataset_name=Path(model_checkpoint).parent.parent.name,
            n_imgs=config["output"]["N"],
            score=score,
        )
        return writer

    def get_group_name_for_config(self, train_cfg):
        decoder = train_cfg["arch"]["type"]
        encoder = train_cfg["arch"]["args"]["encoder_name"]
        return f"{encoder}-{decoder}"

    def check_score(self, checkpoint):
        best_score = self.extract_score(checkpoint)
        self.logger.info(f"Best score: {best_score}")
        if best_score < self.cfg["score_threshold"]:
            msg = f"Skipping low scoring model"
            self.logger.warning(msg)
            raise Exception(msg)
        return best_score

    def extract_score(self, checkpoint):
        best_score = checkpoint["monitor_best"]
        if isinstance(best_score, torch.Tensor):
            best_score = best_score.item()
        return best_score

    def load_checkpoint(self, path, device):
        self.logger.info(f"Loading checkpoint: {path}")
        checkpoint = torch.load(path, map_location=device)
        return checkpoint

    def setup_device(self, device):
        if device is None or device == "cpu":
            return torch.device("cpu")
        else:
            return torch.device(device)
