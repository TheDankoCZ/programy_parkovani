import os
from PyQt5.QtWidgets import QLabel, QSizePolicy, QToolTip
from PyQt5.QtCore import QTimer, Qt, QRect
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QMouseEvent, QCursor, QKeyEvent
import cv2  # install opencv-python


class CustomVideoWidget(QLabel):
    def __init__(self, parent=None, max_width=None, max_height=None, labels_dir=None):
        super().__init__(parent)
        self.box_coordinates = []
        self.cap = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAlignment(Qt.AlignCenter)
        self.bounding_boxes = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.is_paused = False
        self.video_name = ""
        self.frame_index = 1
        self.labels_dir = labels_dir

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
        else:
            print(f"Video {video_path} loaded successfully.")
        self.timer.start(30)  # Adjust based on video frame rate
        self.frame_index = 1
        self.video_name = os.path.basename(video_path).split('.')[0]
        self.resume_video()

    def read_bounding_boxes(self, frame_index):
        if not self.labels_dir:
            return []

        label_file = os.path.join(self.labels_dir, f"{self.video_name}_{frame_index}.txt")
        if not os.path.exists(label_file):
            print(f"Label file {label_file} does not exist.")
            return []

        bounding_boxes = []
        with open(label_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 7:
                    class_id, x_center, y_center, width, height, confidence, vehicle_id = map(float, parts[:7])
                    bounding_boxes.append((class_id, x_center, y_center, width, height, confidence, vehicle_id))

        return bounding_boxes

    def update_frame(self):
        self.setFocus()
        if self.cap is not None and self.cap.isOpened() and not self.is_paused:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channel = frame.shape
                step = channel * width

                # Read bounding boxes for the current frame
                self.bounding_boxes = self.read_bounding_boxes(self.frame_index)
                print(f"Frame {self.frame_index}: {len(self.bounding_boxes)} bounding boxes")
                self.frame_index += 1

                q_img = QImage(frame.data, width, height, step, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)

                # Scale the pixmap to fit within the maximum width and height while maintaining the aspect ratio
                if self.max_width is not None and self.max_height is not None:
                    pixmap = pixmap.scaled(self.max_width, self.max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                # Draw bounding boxes on the pixmap
                painter = QPainter(pixmap)
                pen = QPen(QColor(255, 0, 0), 2)
                painter.setPen(pen)
                self.box_coordinates = []  # Store box coordinates separately
                for box in self.bounding_boxes:
                    class_id, x_center, y_center, box_width, box_height, confidence, vehicle_id = box
                    top_left_x = (x_center - box_width / 2) * pixmap.width()
                    top_left_y = (y_center - box_height / 2) * pixmap.height()
                    rect_width = box_width * pixmap.width()
                    rect_height = box_height * pixmap.height()
                    painter.drawRect(top_left_x, top_left_y, rect_width, rect_height)
                    self.box_coordinates.append((class_id, confidence, top_left_x, top_left_y, rect_width, rect_height, vehicle_id))
                painter.end()

                self.setPixmap(pixmap)
            else:
                print("Video ended or frame not available.")
                self.cap.release()
                self.timer.stop()
        else:
            print("Video capture not opened or is paused.")

    def mousePressEvent(self, event: QMouseEvent):
        if self.box_coordinates:
            x = event.x()
            y = event.y()
            box_clicked = False
            for class_id, confidence, top_left_x, top_left_y, rect_width, rect_height, vehicle_id in self.box_coordinates:
                if top_left_x <= x <= top_left_x + rect_width and top_left_y <= y <= top_left_y + rect_height:
                    QToolTip.showText(event.globalPos(), f"Vehicle ID: {vehicle_id}, Confidence: {confidence}", self, QRect(), 5000)
                    box_clicked = True
                    break
            if not box_clicked:
                QToolTip.hideText()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.box_coordinates:
            x = event.x()
            y = event.y()
            hovering_over_box = False
            for class_id, confidence, top_left_x, top_left_y, rect_width, rect_height, vehicle_id in self.box_coordinates:
                if top_left_x <= x <= top_left_x + rect_width and top_left_y <= y <= top_left_y + rect_height:
                    self.setCursor(QCursor(Qt.PointingHandCursor))
                    hovering_over_box = True
                    break
            if not hovering_over_box:
                self.setCursor(QCursor(Qt.ArrowCursor))

    def enterEvent(self, event):
        self.pause_video()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space:
            self.pause_unpause()
        event.accept()  # Ensure the event is handled by this widget

    def pause_unpause(self):
        if self.is_paused:
            self.resume_video()
        else:
            self.pause_video()

    def pause_video(self):
        self.is_paused = True
        self.timer.stop()

    def resume_video(self):
        self.is_paused = False
        self.timer.start(30)
