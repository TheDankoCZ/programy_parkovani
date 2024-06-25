import os
from PyQt5.QtWidgets import QLabel, QSizePolicy, QToolTip, QSlider, QVBoxLayout, QSpacerItem
from PyQt5.QtCore import QTimer, Qt, QRect
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QMouseEvent, QCursor, QKeyEvent
import cv2  # install opencv-python


class CustomVideoWidget(QLabel):
    def __init__(self, parent=None, max_width=None, max_height=None, labels_dir=None):
        super().__init__(parent)
        self.box_coordinates = []
        self.bounding_boxes = {}
        self.cap = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAlignment(Qt.AlignCenter)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.is_paused = False
        self.is_seeking = False

        self.video_name = ""
        self.frame_index = 1
        self.labels_dir = labels_dir

        self.selected_vehicle_id = None

        self.spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.progress_bar = QSlider(Qt.Horizontal, self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.sliderMoved.connect(self.seek_video)
        self.progress_bar.sliderReleased.connect(self.slider_released)
        self.layout = QVBoxLayout(self)
        self.layout.addItem(self.spacer)
        self.layout.addWidget(self.progress_bar)
        self.setLayout(self.layout)
        self.video_duration = 0
        self.highlighted_frames = []

        # Set maximum size constraints if provided
        if max_width is not None:
            self.setMaximumWidth(max_width)
        if max_height is not None:
            self.setMaximumHeight(max_height)

        self.max_width = max_width
        self.max_height = max_height

        self.frame_update_callback = None
        self.bounding_box_callback = None

    def set_frame_update_callback(self, callback):
        self.frame_update_callback = callback

    def set_bounding_box_callback(self, callback):
        self.bounding_box_callback = callback

    def load_video(self, video_path):
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            print("Error: Could not open video.")
        else:
            print(f"Video {video_path} loaded successfully.")
        self.timer.start(30)  # Adjust based on video frame rate
        self.frame_index = 1
        self.video_duration = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.progress_bar.setRange(0, self.video_duration)
        self.parse_label_files()
        self.video_name = os.path.basename(video_path).split('.')[0]
        self.resume_video()

    def parse_label_files(self):
        self.bounding_boxes = {}
        if not self.labels_dir:
            return

        for label_file in os.listdir(self.labels_dir):
            if label_file.endswith('.txt'):
                file_path = os.path.join(self.labels_dir, label_file)
                with open(file_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 7:
                            frame_index = int(parts[0])
                            class_id = int(parts[1])
                            x_center, y_center = float(parts[2]), float(parts[3])
                            width, height = float(parts[4]), float(parts[5])
                            confidence = parts[6]
                            if confidence != 'interpolated':
                                confidence = float(confidence)
                            # vehicle_id is the name of the txt file without the extension
                            vehicle_id = int(os.path.basename(label_file).split('.')[0])

                            if frame_index not in self.bounding_boxes:
                                self.bounding_boxes[frame_index] = []
                            self.bounding_boxes[frame_index].append(
                                (class_id, x_center, y_center, width, height, confidence, vehicle_id)
                            )

    def read_bounding_boxes(self, frame_index):
        return self.bounding_boxes.get(frame_index, [])

    def update_frame(self):
        self.setFocus()
        if self.cap is not None and self.cap.isOpened() and not self.is_paused and not self.is_seeking:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channel = frame.shape
                step = channel * width

                # Read bounding boxes for the current frame
                current_frame_bounding_boxes = self.read_bounding_boxes(self.frame_index)
                print(f"Frame {self.frame_index}: {len(current_frame_bounding_boxes)} bounding boxes")
                self.frame_index += 1

                q_img = QImage(frame.data, width, height, step, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)

                # Scale the pixmap to fit within the maximum width and height while maintaining the aspect ratio
                if self.max_width is not None and self.max_height is not None:
                    pixmap = pixmap.scaled(self.max_width, self.max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                # Draw bounding boxes on the pixmap
                painter = QPainter(pixmap)
                pen_nehotovo = QPen(QColor(255, 0, 0), 2)
                pen_selected = QPen(QColor(0, 255, 0), 2)
                pen_hotovo = QPen(QColor(0, 0, 255), 2)
                pen_disabled = QPen(QColor(128, 128, 128), 2)
                self.box_coordinates = []  # Store box coordinates separately
                for box in current_frame_bounding_boxes:
                    class_id, x_center, y_center, box_width, box_height, confidence, vehicle_id = box
                    if vehicle_id == self.selected_vehicle_id:
                        painter.setPen(pen_selected)
                    else:
                        painter.setPen(pen_nehotovo)
                    top_left_x = (x_center - box_width / 2) * pixmap.width()
                    top_left_y = (y_center - box_height / 2) * pixmap.height()
                    rect_width = box_width * pixmap.width()
                    rect_height = box_height * pixmap.height()
                    painter.drawRect(QRect(top_left_x, top_left_y, rect_width, rect_height))
                    self.box_coordinates.append((class_id, confidence, top_left_x, top_left_y, rect_width, rect_height, vehicle_id))
                painter.end()

                self.setPixmap(pixmap)
                # align pixmap to top
                self.setAlignment(Qt.AlignTop)

                if self.frame_update_callback:
                    self.frame_update_callback(self.frame_index)

                self.progress_bar.setValue(self.frame_index)

            else:
                print("Video ended or frame not available.")
                self.cap.release()
                self.timer.stop()
        else:
            print("Video capture not opened or is paused (seeking).")

    def seek_video(self, position):
        if self.cap is not None and self.cap.isOpened():
            print(f"Seeking to position: {position}")
            self.is_seeking = True
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            self.frame_index = position
            self.update_frame()
            self.is_seeking = False

    def mousePressEvent(self, event: QMouseEvent):
        self.pause_video()
        if self.box_coordinates:
            x = event.x()
            y = event.y()
            box_clicked = False
            for class_id, confidence, top_left_x, top_left_y, rect_width, rect_height, vehicle_id in self.box_coordinates:
                if top_left_x <= x <= top_left_x + rect_width and top_left_y <= y <= top_left_y + rect_height:
                    if self.bounding_box_callback:
                        self.bounding_box_callback(vehicle_id)
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

    def slider_released(self):
        if self.is_paused:
            self.resume_video()
            self.update_frame()
            self.pause_video()
        else:
            self.resume_video()

    def set_highlighted_frames(self, frames):
        self.highlighted_frames = frames
        self.update_progress_bar()
        self.resume_video()
        self.update_frame()
        self.pause_video()
        self.seek_video(self.frame_index - 1)

    def update_progress_bar(self):
        # Custom paint on progress bar to highlight specific frames
        class HighlightedSlider(QSlider):
            def __init__(self, highlighted_frames, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.highlighted_frames = highlighted_frames
                self.setValue(highlighted_frames[0] if highlighted_frames else 0)

            def paintEvent(self, event):
                painter = QPainter(self)
                pen = QPen(QColor(71, 187, 237), 3)
                painter.setPen(pen)
                for frame in self.highlighted_frames:
                    position = int(frame / self.maximum() * self.width())
                    painter.drawLine(position, 0, position, 8)

                super().paintEvent(event)  # Draw the default slider on top of the highlighted frames

        self.layout.removeWidget(self.progress_bar)
        self.progress_bar.destroy()
        self.progress_bar = HighlightedSlider(self.highlighted_frames, Qt.Horizontal, self)
        self.progress_bar.setRange(0, self.video_duration)
        self.progress_bar.sliderMoved.connect(self.seek_video)
        self.progress_bar.sliderReleased.connect(self.slider_released)
        self.layout.addWidget(self.progress_bar)
