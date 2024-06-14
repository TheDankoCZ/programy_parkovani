from PyQt5.QtWidgets import QLabel, QSizePolicy
from PyQt5.QtCore import QTimer, Qt, QRect
from PyQt5.QtGui import QImage, QPixmap
import cv2  # install opencv-python

class CustomVideoWidget(QLabel):
    def __init__(self, parent=None, max_width=None, max_height=None):
        super().__init__(parent)
        self.cap = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignCenter)
        self.bounding_boxes = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

        # Set maximum size constraints if provided
        if max_width is not None:
            self.setMaximumWidth(max_width)
        if max_height is not None:
            self.setMaximumHeight(max_height)

        self.max_width = max_width
        self.max_height = max_height

    def load_video(self, video_path):
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            print("Error: Could not open video.")
        self.timer.start(30)  # Adjust based on video frame rate

    def update_frame(self):
        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channel = frame.shape
                step = channel * width
                q_img = QImage(frame.data, width, height, step, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)

                # Scale the pixmap to fit within the maximum width and height while maintaining the aspect ratio
                if self.max_width is not None and self.max_height is not None:
                    pixmap = pixmap.scaled(self.max_width, self.max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                self.setPixmap(pixmap)
            else:
                self.cap.release()
                self.timer.stop()

    def setBoundingBoxes(self, boxes):
        self.bounding_boxes = boxes
        self.update()
