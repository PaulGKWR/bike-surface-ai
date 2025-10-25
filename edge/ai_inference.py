"""
AI Inference Module for Surface Detection
Handles YOLOv8/TensorRT inference for detecting surface types and damages.
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SurfaceDetector:
    """YOLOv8/TensorRT surface and damage detection"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize surface detector
        
        Args:
            config: Model configuration dictionary
        """
        self.model_path = config.get('path', 'models/surface_detection.engine')
        self.confidence_threshold = config.get('confidence_threshold', 0.5)
        self.nms_threshold = config.get('nms_threshold', 0.4)
        self.input_size = tuple(config.get('input_size', [640, 640]))
        self.class_names = config.get('classes', [
            'asphalt', 'concrete', 'gravel', 'cobblestone',
            'pothole', 'crack', 'patch', 'bump', 'debris'
        ])
        
        self.model = None
        self.use_tensorrt = False
        self.load_model()
    
    def load_model(self):
        """Load the detection model (TensorRT or ONNX fallback)"""
        model_path = Path(self.model_path)
        
        try:
            # Try to load TensorRT engine (for Jetson)
            if model_path.suffix == '.engine':
                self.model = self._load_tensorrt_engine(model_path)
                self.use_tensorrt = True
                logger.info(f"Loaded TensorRT engine from {model_path}")
            
            # Fallback to ONNX
            elif model_path.suffix == '.onnx':
                self.model = self._load_onnx_model(model_path)
                logger.info(f"Loaded ONNX model from {model_path}")
            
            # Fallback to PyTorch/Ultralytics
            else:
                self.model = self._load_pytorch_model(model_path)
                logger.info(f"Loaded PyTorch model from {model_path}")
        
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            logger.warning("Using mock detector for testing")
            self.model = None
    
    def _load_tensorrt_engine(self, model_path: Path):
        """Load TensorRT engine (Jetson optimized)"""
        try:
            import tensorrt as trt
            import pycuda.driver as cuda
            import pycuda.autoinit
            
            TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
            
            with open(model_path, 'rb') as f:
                engine_data = f.read()
            
            runtime = trt.Runtime(TRT_LOGGER)
            engine = runtime.deserialize_cuda_engine(engine_data)
            
            return engine
        
        except ImportError:
            logger.warning("TensorRT not available, falling back to ONNX")
            return None
    
    def _load_onnx_model(self, model_path: Path):
        """Load ONNX model"""
        try:
            import onnxruntime as ort
            
            session = ort.InferenceSession(
                str(model_path),
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            return session
        
        except ImportError:
            logger.warning("ONNX Runtime not available")
            return None
    
    def _load_pytorch_model(self, model_path: Path):
        """Load PyTorch model using Ultralytics"""
        try:
            from ultralytics import YOLO
            model = YOLO(str(model_path))
            return model
        
        except ImportError:
            logger.warning("Ultralytics not available")
            return None
    
    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run detection on a single frame
        
        Args:
            frame: Input image (BGR format from OpenCV)
            
        Returns:
            List of detection dictionaries with class, confidence, bbox
        """
        if self.model is None:
            return self._mock_detect(frame)
        
        # Preprocess frame
        input_tensor = self._preprocess(frame)
        
        # Run inference based on model type
        if self.use_tensorrt:
            detections = self._infer_tensorrt(input_tensor)
        elif hasattr(self.model, 'run'):  # ONNX
            detections = self._infer_onnx(input_tensor)
        else:  # PyTorch/Ultralytics
            detections = self._infer_pytorch(frame)
        
        return detections
    
    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for model input"""
        # Resize to model input size
        resized = cv2.resize(frame, self.input_size)
        
        # Convert BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1] and transpose to CHW format
        normalized = rgb.astype(np.float32) / 255.0
        transposed = np.transpose(normalized, (2, 0, 1))
        
        # Add batch dimension
        batched = np.expand_dims(transposed, axis=0)
        
        return batched
    
    def _infer_tensorrt(self, input_tensor: np.ndarray) -> List[Dict[str, Any]]:
        """Run TensorRT inference"""
        # TensorRT inference implementation
        # This is a placeholder - actual implementation depends on engine structure
        logger.warning("TensorRT inference not fully implemented")
        return []
    
    def _infer_onnx(self, input_tensor: np.ndarray) -> List[Dict[str, Any]]:
        """Run ONNX inference"""
        input_name = self.model.get_inputs()[0].name
        outputs = self.model.run(None, {input_name: input_tensor})
        
        # Parse YOLO outputs
        detections = self._parse_yolo_outputs(outputs[0])
        return detections
    
    def _infer_pytorch(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run PyTorch inference using Ultralytics"""
        results = self.model(frame, conf=self.confidence_threshold, iou=self.nms_threshold)
        
        detections = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                detection = {
                    'class': self.class_names[int(box.cls)],
                    'confidence': float(box.conf),
                    'bbox': box.xyxy[0].tolist(),  # [x1, y1, x2, y2]
                }
                detections.append(detection)
        
        return detections
    
    def _parse_yolo_outputs(self, outputs: np.ndarray) -> List[Dict[str, Any]]:
        """Parse YOLO model outputs"""
        detections = []
        
        # YOLO output format: [batch, num_detections, 5 + num_classes]
        # [x, y, w, h, objectness, class_scores...]
        
        for detection in outputs[0]:
            objectness = detection[4]
            if objectness < self.confidence_threshold:
                continue
            
            class_scores = detection[5:]
            class_id = np.argmax(class_scores)
            confidence = class_scores[class_id] * objectness
            
            if confidence < self.confidence_threshold:
                continue
            
            # Convert from YOLO format (center x, center y, w, h) to (x1, y1, x2, y2)
            x_center, y_center, width, height = detection[:4]
            x1 = int((x_center - width / 2) * self.input_size[0])
            y1 = int((y_center - height / 2) * self.input_size[1])
            x2 = int((x_center + width / 2) * self.input_size[0])
            y2 = int((y_center + height / 2) * self.input_size[1])
            
            detections.append({
                'class': self.class_names[class_id],
                'confidence': float(confidence),
                'bbox': [x1, y1, x2, y2]
            })
        
        # Apply NMS
        detections = self._apply_nms(detections)
        return detections
    
    def _apply_nms(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply Non-Maximum Suppression"""
        if not detections:
            return []
        
        boxes = np.array([d['bbox'] for d in detections])
        scores = np.array([d['confidence'] for d in detections])
        
        indices = cv2.dnn.NMSBoxes(
            boxes.tolist(),
            scores.tolist(),
            self.confidence_threshold,
            self.nms_threshold
        )
        
        if len(indices) > 0:
            return [detections[i] for i in indices.flatten()]
        return []
    
    def _mock_detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Mock detection for testing without model"""
        import random
        
        # Simulate 1-3 random detections
        num_detections = random.randint(0, 3)
        detections = []
        
        h, w = frame.shape[:2]
        
        for _ in range(num_detections):
            class_name = random.choice(self.class_names)
            confidence = random.uniform(0.5, 0.95)
            
            # Random bbox
            x1 = random.randint(0, w - 100)
            y1 = random.randint(0, h - 100)
            x2 = x1 + random.randint(50, 200)
            y2 = y1 + random.randint(50, 200)
            
            detections.append({
                'class': class_name,
                'confidence': confidence,
                'bbox': [x1, y1, x2, y2]
            })
        
        return detections
    
    def visualize_detections(self, frame: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        """
        Draw detection boxes on frame
        
        Args:
            frame: Input image
            detections: List of detections
            
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        
        for detection in detections:
            bbox = detection['bbox']
            class_name = detection['class']
            confidence = detection['confidence']
            
            # Draw bounding box
            x1, y1, x2, y2 = map(int, bbox)
            color = self._get_class_color(class_name)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{class_name}: {confidence:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(
                annotated,
                (x1, y1 - label_size[1] - 10),
                (x1 + label_size[0], y1),
                color,
                -1
            )
            cv2.putText(
                annotated,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                2
            )
        
        return annotated
    
    def _get_class_color(self, class_name: str) -> Tuple[int, int, int]:
        """Get color for each class"""
        color_map = {
            'pothole': (0, 0, 255),      # Red
            'crack': (0, 165, 255),      # Orange
            'patch': (0, 255, 255),      # Yellow
            'bump': (0, 255, 0),         # Green
            'debris': (255, 20, 147),    # Pink
            'asphalt': (50, 50, 50),     # Dark gray
            'concrete': (150, 150, 150), # Light gray
            'gravel': (19, 69, 139),     # Brown
            'cobblestone': (45, 135, 205), # Orange-brown
        }
        return color_map.get(class_name, (255, 255, 255))
