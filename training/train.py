"""
YOLOv8 Training Script for Surface and Damage Detection
Train a custom YOLOv8 model for detecting road surfaces and damages.
"""

import os
import yaml
from pathlib import Path
import torch
from ultralytics import YOLO
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_training_config(config_path='yolov8_config.yaml'):
    """Load training configuration from YAML file"""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def setup_directories():
    """Create necessary directories for training"""
    dirs = ['runs', 'models', 'datasets']
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
    logger.info("Directories created")


def train_surface_detection_model(config):
    """
    Train YOLOv8 model for surface and damage detection
    
    Args:
        config: Training configuration dictionary
    """
    logger.info("=" * 60)
    logger.info("Starting YOLOv8 Training for Bike Surface AI")
    logger.info("=" * 60)
    
    # Initialize YOLO model
    model_size = config.get('model_size', 'yolov8n.pt')
    logger.info(f"Initializing model: {model_size}")
    model = YOLO(model_size)
    
    # Check for GPU
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info(f"Using device: {device}")
    
    if device == 'cpu':
        logger.warning("Training on CPU will be very slow. Consider using a GPU.")
    
    # Prepare training arguments
    train_args = {
        'data': config['data_path'],
        'epochs': config['epochs'],
        'imgsz': config['image_size'],
        'batch': config['batch_size'],
        'device': device,
        'workers': config['workers'],
        'project': 'runs/detect',
        'name': config.get('experiment_name', 'bike_surface_v1'),
        'exist_ok': True,
        'pretrained': True,
        'optimizer': config.get('optimizer', 'SGD'),
        'lr0': config['learning_rate'],
        'patience': config.get('patience', 50),
        'save': True,
        'save_period': config.get('save_period', 10),
        'cache': False,
        'verbose': True,
        'seed': config.get('seed', 0),
        'deterministic': True,
        'plots': True,
        'val': True,
    }
    
    # Add data augmentation parameters
    augmentation = config.get('augmentation', {})
    if augmentation:
        train_args.update({
            'hsv_h': augmentation.get('hsv_h', 0.015),
            'hsv_s': augmentation.get('hsv_s', 0.7),
            'hsv_v': augmentation.get('hsv_v', 0.4),
            'degrees': augmentation.get('degrees', 5.0),
            'translate': augmentation.get('translate', 0.1),
            'scale': augmentation.get('scale', 0.5),
            'shear': augmentation.get('shear', 0.0),
            'perspective': augmentation.get('perspective', 0.0),
            'flipud': augmentation.get('flipud', 0.0),
            'fliplr': augmentation.get('fliplr', 0.5),
            'mosaic': augmentation.get('mosaic', 1.0),
            'mixup': augmentation.get('mixup', 0.1),
        })
    
    logger.info("Training configuration:")
    for key, value in train_args.items():
        logger.info(f"  {key}: {value}")
    
    # Train the model
    logger.info("\nStarting training...")
    try:
        results = model.train(**train_args)
        
        logger.info("=" * 60)
        logger.info("Training completed successfully!")
        logger.info("=" * 60)
        
        # Print results
        if hasattr(results, 'results_dict'):
            logger.info("\nTraining Results:")
            for key, value in results.results_dict.items():
                logger.info(f"  {key}: {value}")
        
        # Save best model
        best_model_path = Path('runs/detect') / train_args['name'] / 'weights' / 'best.pt'
        if best_model_path.exists():
            # Copy to models directory
            import shutil
            output_path = Path('models') / f"surface_detection_best.pt"
            shutil.copy(best_model_path, output_path)
            logger.info(f"\nBest model saved to: {output_path}")
        
        return results
    
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        raise


def validate_model(model_path, data_yaml):
    """
    Validate trained model
    
    Args:
        model_path: Path to trained model
        data_yaml: Path to data configuration
    """
    logger.info(f"\nValidating model: {model_path}")
    
    model = YOLO(model_path)
    results = model.val(data=data_yaml)
    
    logger.info("\nValidation Results:")
    logger.info(f"  mAP50: {results.box.map50:.4f}")
    logger.info(f"  mAP50-95: {results.box.map:.4f}")
    logger.info(f"  Precision: {results.box.mp:.4f}")
    logger.info(f"  Recall: {results.box.mr:.4f}")
    
    return results


def create_sample_dataset_config():
    """Create a sample dataset configuration file"""
    sample_config = {
        'path': '../datasets/surface_dataset',
        'train': 'images/train',
        'val': 'images/val',
        'test': 'images/test',
        'nc': 9,  # number of classes
        'names': [
            'asphalt',
            'concrete',
            'gravel',
            'cobblestone',
            'pothole',
            'crack',
            'patch',
            'bump',
            'debris'
        ]
    }
    
    output_path = 'datasets/surface_dataset.yaml'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        yaml.dump(sample_config, f, default_flow_style=False)
    
    logger.info(f"Sample dataset config created: {output_path}")
    logger.info("NOTE: Update this file with your actual dataset paths!")


def main():
    """Main training pipeline"""
    # Setup
    setup_directories()
    
    # Load configuration
    try:
        config = load_training_config('yolov8_config.yaml')
    except FileNotFoundError:
        logger.error("yolov8_config.yaml not found!")
        logger.info("Please ensure yolov8_config.yaml exists in the training directory")
        return
    
    # Check if dataset exists
    data_path = config['data_path']
    if not os.path.exists(data_path):
        logger.warning(f"Dataset configuration not found: {data_path}")
        logger.info("Creating sample dataset configuration...")
        create_sample_dataset_config()
        logger.info("\nPlease prepare your dataset and update the configuration file!")
        logger.info("Dataset structure should be:")
        logger.info("  datasets/surface_dataset/")
        logger.info("    ├── images/")
        logger.info("    │   ├── train/")
        logger.info("    │   ├── val/")
        logger.info("    │   └── test/")
        logger.info("    └── labels/")
        logger.info("        ├── train/")
        logger.info("        ├── val/")
        logger.info("        └── test/")
        return
    
    # Train model
    results = train_surface_detection_model(config)
    
    # Validate model
    best_model = Path('models') / 'surface_detection_best.pt'
    if best_model.exists():
        validate_model(str(best_model), data_path)
    
    logger.info("\n" + "=" * 60)
    logger.info("Training pipeline completed!")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. Export model to ONNX: python export_onnx.py")
    logger.info("2. Convert to TensorRT: python convert_tensorrt.py")
    logger.info("3. Deploy to Jetson Orin Nano")


if __name__ == "__main__":
    main()
