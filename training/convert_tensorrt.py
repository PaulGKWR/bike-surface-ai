"""
Convert ONNX Model to TensorRT Engine
Optimize model for deployment on Jetson Orin Nano.
"""

import os
import yaml
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config(config_path='yolov8_config.yaml'):
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def convert_to_tensorrt(onnx_path, output_path, **trt_args):
    """
    Convert ONNX model to TensorRT engine
    
    Args:
        onnx_path: Path to ONNX model
        output_path: Path to save TensorRT engine
        **trt_args: TensorRT conversion arguments
    
    Returns:
        Path to TensorRT engine
    """
    logger.info("=" * 60)
    logger.info("Converting ONNX to TensorRT Engine")
    logger.info("=" * 60)
    logger.info("\nNOTE: This script must be run on the Jetson Orin Nano")
    logger.info("      or a system with TensorRT installed!")
    
    try:
        import tensorrt as trt
        
        TRT_LOGGER = trt.Logger(trt.Logger.INFO)
        
        logger.info(f"\nTensorRT Version: {trt.__version__}")
        logger.info(f"Loading ONNX model: {onnx_path}")
        
        # Create builder
        builder = trt.Builder(TRT_LOGGER)
        network = builder.create_network(
            1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        )
        parser = trt.OnnxParser(network, TRT_LOGGER)
        
        # Parse ONNX model
        with open(onnx_path, 'rb') as f:
            if not parser.parse(f.read()):
                logger.error("Failed to parse ONNX model")
                for error in range(parser.num_errors):
                    logger.error(parser.get_error(error))
                return None
        
        logger.info("✓ ONNX model parsed successfully")
        
        # Create builder config
        config = builder.create_builder_config()
        
        # Set workspace size
        workspace_size = trt_args.get('workspace_size', 4) * (1 << 30)  # GB to bytes
        config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, workspace_size)
        logger.info(f"Workspace size: {workspace_size / (1<<30):.1f} GB")
        
        # Enable FP16 precision if supported
        if trt_args.get('fp16', True) and builder.platform_has_fast_fp16:
            config.set_flag(trt.BuilderFlag.FP16)
            logger.info("✓ FP16 mode enabled")
        
        # Enable INT8 precision if requested
        if trt_args.get('int8', False) and builder.platform_has_fast_int8:
            config.set_flag(trt.BuilderFlag.INT8)
            logger.info("✓ INT8 mode enabled")
            logger.warning("INT8 calibration required for optimal results")
        
        # Build engine
        logger.info("\nBuilding TensorRT engine...")
        logger.info("This may take several minutes...")
        
        serialized_engine = builder.build_serialized_network(network, config)
        
        if serialized_engine is None:
            logger.error("Failed to build TensorRT engine")
            return None
        
        # Save engine
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(serialized_engine)
        
        logger.info(f"\n✓ TensorRT engine saved to: {output_path}")
        
        # Get file size
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        logger.info(f"Engine size: {file_size:.2f} MB")
        
        return output_path
    
    except ImportError:
        logger.error("TensorRT not available!")
        logger.info("\nTensorRT is included with NVIDIA JetPack on Jetson devices.")
        logger.info("For other systems, install TensorRT from:")
        logger.info("https://developer.nvidia.com/tensorrt")
        logger.info("\nAlternatively, use the ONNX model directly with onnxruntime-gpu")
        return None
    
    except Exception as e:
        logger.error(f"Conversion failed: {e}", exc_info=True)
        return None


def convert_using_trtexec(onnx_path, output_path, **trt_args):
    """
    Convert ONNX to TensorRT using trtexec command-line tool
    
    Args:
        onnx_path: Path to ONNX model
        output_path: Path to save TensorRT engine
        **trt_args: TensorRT conversion arguments
    
    Returns:
        Path to TensorRT engine or None
    """
    logger.info("=" * 60)
    logger.info("Converting using trtexec (command-line tool)")
    logger.info("=" * 60)
    
    # Build trtexec command
    cmd = [
        "trtexec",
        f"--onnx={onnx_path}",
        f"--saveEngine={output_path}",
    ]
    
    # Add workspace size
    workspace_mb = trt_args.get('workspace_size', 4) * 1024
    cmd.append(f"--workspace={workspace_mb}")
    
    # Add FP16
    if trt_args.get('fp16', True):
        cmd.append("--fp16")
    
    # Add INT8
    if trt_args.get('int8', False):
        cmd.append("--int8")
    
    # Add verbosity
    cmd.append("--verbose")
    
    cmd_str = " ".join(cmd)
    logger.info(f"\nCommand: {cmd_str}")
    logger.info("\nExecuting trtexec...")
    logger.info("This may take several minutes...\n")
    
    import subprocess
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        logger.info(result.stdout)
        logger.info(f"\n✓ Conversion successful!")
        logger.info(f"Engine saved to: {output_path}")
        
        return output_path
    
    except subprocess.CalledProcessError as e:
        logger.error(f"trtexec failed with return code {e.returncode}")
        logger.error(e.stderr)
        return None
    except FileNotFoundError:
        logger.error("trtexec not found!")
        logger.info("trtexec is included with TensorRT and JetPack")
        return None


def main():
    """Main conversion pipeline"""
    # Load configuration
    try:
        config = load_config('yolov8_config.yaml')
    except FileNotFoundError:
        logger.error("yolov8_config.yaml not found!")
        return
    
    # Find ONNX model
    onnx_path = Path('models') / 'surface_detection_best.onnx'
    
    if not onnx_path.exists():
        logger.error(f"ONNX model not found: {onnx_path}")
        logger.info("Please export to ONNX first using export_onnx.py")
        return
    
    # Output path for TensorRT engine
    trt_path = Path('models') / 'surface_detection.engine'
    
    # Get TensorRT configuration
    trt_config = config.get('export', {}).get('tensorrt', {})
    
    logger.info(f"ONNX model: {onnx_path}")
    logger.info(f"Output engine: {trt_path}")
    logger.info(f"Configuration: {trt_config}")
    
    # Try Python API first, fallback to trtexec
    engine_path = convert_to_tensorrt(
        str(onnx_path),
        str(trt_path),
        **trt_config
    )
    
    if engine_path is None:
        logger.info("\nTrying trtexec command-line tool...")
        engine_path = convert_using_trtexec(
            str(onnx_path),
            str(trt_path),
            **trt_config
        )
    
    if engine_path:
        logger.info("\n" + "=" * 60)
        logger.info("Conversion completed successfully!")
        logger.info("=" * 60)
        logger.info(f"\nTensorRT engine ready for deployment:")
        logger.info(f"  {engine_path}")
        logger.info("\nNext steps:")
        logger.info("1. Copy engine to Jetson Orin Nano")
        logger.info("2. Update edge/config.yaml with engine path")
        logger.info("3. Run edge system: python edge/main.py")
    else:
        logger.error("\nConversion failed!")
        logger.info("You can still use the ONNX model with onnxruntime-gpu")


if __name__ == "__main__":
    main()
