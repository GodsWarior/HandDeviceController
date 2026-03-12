import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


CONFIG_PATH = Path(__file__).parent / "config.json"


@dataclass
class CameraConfig:
    device_index: int = 0
    frame_width: int = 640
    frame_height: int = 480
    fps: int = 30


@dataclass
class SensitivityConfig:
    x: float = 1.8
    y: float = 1.5


@dataclass
class ThresholdConfig:
    move: float = 0.05
    click: float = 0.06


@dataclass
class OptimizationConfig:
    minimize_optimization_default: bool = True
    background_mode_default: bool = False


@dataclass
class AppConfig:
    camera: CameraConfig
    sensitivity: SensitivityConfig
    thresholds: ThresholdConfig
    dead_zone_ratio: float
    click_cooldown_seconds: float
    smoothing: int
    optimization: OptimizationConfig


def _merge_dict(defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> AppConfig:
    """
    Загружает конфигурацию из config.json.
    Если файл отсутствует или повреждён — используются значения по умолчанию.
    """
    default_dict = {
        "camera": {
            "device_index": 0,
            "frame_width": 640,
            "frame_height": 480,
            "fps": 30,
        },
        "sensitivity": {"x": 1.8, "y": 1.5},
        "thresholds": {"move": 0.05, "click": 0.06},
        "dead_zone_ratio": 0.1,
        "click_cooldown_seconds": 0.5,
        "smoothing": 3,
        "optimization": {
            "minimize_optimization_default": True,
            "background_mode_default": False,
        },
    }

    if not CONFIG_PATH.exists():
        data = default_dict
    else:
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                file_data = json.load(f)
            data = _merge_dict(default_dict, file_data)
        except Exception:
            data = default_dict

    camera_cfg = CameraConfig(**data["camera"])
    sens_cfg = SensitivityConfig(**data["sensitivity"])
    thr_cfg = ThresholdConfig(**data["thresholds"])
    opt_cfg = OptimizationConfig(**data["optimization"])

    return AppConfig(
        camera=camera_cfg,
        sensitivity=sens_cfg,
        thresholds=thr_cfg,
        dead_zone_ratio=data["dead_zone_ratio"],
        click_cooldown_seconds=data["click_cooldown_seconds"],
        smoothing=data["smoothing"],
        optimization=opt_cfg,
    )


