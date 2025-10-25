"""
Export YOLOv8 Model to ONNX Format
Convert trained PyTorch model to ONNX for deployment.
"""

import os
import yaml
from pathlib import Path
from ultralytics import YOLO
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config(config_path='yolov8_config.yaml'):
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def export_to_onnx(model_path, output_dir='models', **export_args):
    """
    Export YOLOv8 model to ONNX format
    
    Args:
        model_path: Path to trained PyTorch model (.pt)
        output_dir: Directory to save exported model
        **export_args: Additional export arguments
    
    Returns:
        Path to exported ONNX model
    """
    logger.info("=" * 60)
    logger.info("Exporting YOLOv8 Model to ONNX")
    logger.info("=" * 60)
    
    # Load trained model
    logger.info(f"Loading model from: {model_path}")
    model = YOLO(model_path)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Export to ONNX
    logger.info("\nExporting to ONNX format...")
    logger.info(f"Export arguments: {export_args}")
    
    try:
        export_path = model.export(
            format='onnx',
            **export_args
        )
        
        logger.info(f"\n✓ Model exported successfully!")
        logger.info(f"ONNX model saved to: {export_path}")
        
        # Get file size
        file_size = os.path.getsize(export_path) / (1024 * 1024)  # MB
        logger.info(f"File size: {file_size:.2f} MB")
        
        return export_path
    
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        raise


def validate_onnx_model(onnx_path):
    """
    Validate exported ONNX model
    
    Args:
        onnx_path: Path to ONNX model
    """
    logger.info("\nValidating ONNX model...")
    
    try:
        import onnx
        
        # Load ONNX model
        onnx_model = onnx.load(onnx_path)
        
        # Check model
        onnx.checker.check_model(onnx_model)
        
        logger.info("✓ ONNX model is valid")
        
        # Print model info
        logger.info("\nModel Information:")
        logger.info(f"  IR Version: {onnx_model.ir_version}")
        logger.info(f"  Producer: {onnx_model.producer_name}")
        logger.info(f"  Opset Version: {onnx_model.opset_import[0].version}")
        
        # Print inputs
        logger.info("\nModel Inputs:")
        for input_tensor in onnx_model.graph.input:
            logger.info(f"  Name: {input_tensor.name}")
            logger.info(f"  Shape: {[d.dim_value for d in input_tensor.type.tensor_type.shape.dim]}")
        
        # Print outputs
        logger.info("\nModel Outputs:")
        for output_tensor in onnx_model.graph.output:
            logger.info(f"  Name: {output_tensor.name}")
            logger.info(f"  Shape: {[d.dim_value for d in output_tensor.type.tensor_type.shape.dim]}")
        
        return True
    
    except ImportError:
        logger.warning("ONNX package not installed. Skipping validation.")
        logger.info("Install with: pip install onnx")
        return False
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return False


def test_onnx_inference(onnx_path, test_image=None):
    """
    Test ONNX model inference
    
    Args:
        onnx_path: Path to ONNX model
        test_image: Optional test image path
    """
    logger.info("\nTesting ONNX inference...")
    
    try:
        import onnxruntime as ort
        import numpy as np
        
        # Create inference session
        session = ort.InferenceSession(
            onnx_path,
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
        )
        
        logger.info(f"✓ ONNX Runtime session created")
        logger.info(f"  Providers: {session.get_providers()}")
        
        # Get input details
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape
        logger.info(f"  Input name: {input_name}")
        logger.info(f"  Input shape: {input_shape}")
        
        # Run dummy inference
        dummy_input = np.random.rand(*input_shape).astype(np.float32)
        outputs = session.run(None, {input_name: dummy_input})
        
        logger.info(f"✓ Inference successful")
        logger.info(f"  Output shapes: {[out.shape for out in outputs]}")
        
        return True
    
    except ImportError:
        logger.warning("ONNX Runtime not installed. Skipping inference test.")
        logger.info("Install with: pip install onnxruntime or onnxruntime-gpu")
        return False
    except Exception as e:
        logger.error(f"Inference test failed: {e}")
        return False


def main():
    """Main export pipeline"""
    # Load configuration
    try:
        config = load_config('yolov8_config.yaml')
    except FileNotFoundError:
        logger.error("yolov8_config.yaml not found!")
        return
    
    # Find trained model
    model_path = Path('models') / 'surface_detection_best.pt'
    
    if not model_path.exists():
        # Try alternate location
        model_path = Path('runs/detect') / config['experiment_name'] / 'weights' / 'best.pt'
    
    if not model_path.exists():
        logger.error(f"Trained model not found!")
        logger.info("Please train a model first using train.py")
        return
    
    # Get export configuration
    export_config = config.get('export', {}).get('onnx', {})
    
    # Export to ONNX
    onnx_path = export_to_onnx(
        str(model_path),
        output_dir='models',
        opset=export_config.get('opset_version', 12),
        simplify=export_config.get('simplify', True),
        dynamic=export_config.get('dynamic', False)
    )
    
    # Validate ONNX model
    if onnx_path:
        validate_onnx_model(onnx_path)
        test_onnx_inference(onnx_path)
    
    logger.info("\n" + "=" * 60)
    logger.info("Export completed!")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. Convert to TensorRT: python convert_tensorrt.py")
    logger.info("2. Deploy to Jetson Orin Nano")


if __name__ == "__main__":
    main()
