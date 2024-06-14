import sys
import random

from PyQt5 import QtCore
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage  # install QtWebEngineWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, QRect, QTimer, pyqtSlot, QObject
import folium
from folium import Marker

from mainwindow import Ui_MainWindow  # Import the generated UI class
from custom_video_widget import CustomVideoWidget  # Import the custom video widget class


class WebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print("javaScriptConsoleMessage: ", level, "\n" + message, "\n on line " + str(lineNumber), sourceID)


class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setWindowTitle("Průzkum parkování")

        # Create a custom video widget with max width and height
        max_width = 1900
        max_height = 500
        self.video_widget = CustomVideoWidget(max_width=max_width, max_height=max_height)
        self.videoLayout.addWidget(self.video_widget)

        # Connect play button to media player
        self.zpet_na_zacatek.clicked.connect(self.play_video)

        # Path to video file
        self.video_path = "D:/bakalarka/360 exports/2023-05-24 S04E03-360 11-55-004 (2)_cropped.mp4"

        # Create a timer to update bounding boxes periodically
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_bounding_boxes)
        self.timer.start(1000)  # Update every second

        # Create a QWebEngineView widget
        self.webview = QWebEngineView()
        self.webview.setPage(WebEnginePage(self.webview))
        self.mapLayout.addWidget(self.webview)

        # Create a bridge object to communicate between Python and JavaScript
        channel = QWebChannel(self.webview.page())
        channel.registerObject("bridge", self)
        self.webview.page().setWebChannel(channel)

        # Generate Folium map and convert it to HTML
        self.m = folium.Map(location=[50.77899, 14.21680], zoom_start=19, max_zoom=19, min_zoom=16)
        Marker([50.77899, 14.21680], popup="StrEda").add_to(self.m)

        # Save the map as an HTML file or convert to HTML string
        self.m.save("map.html")

        # Append to the html file
        with open("map.html", "a") as f:
            f.write("<script src=\"qrc:///qtwebchannel/qwebchannel.js\"></script>")

        self.webview.load(QtCore.QUrl.fromLocalFile("/map.html"))

        # Setup map events
        self.webview.loadFinished.connect(self.setup_map_events)

    def setup_map_events(self):
        script = """
            function initializeMapEvents() {
                var mapElementId = document.getElementsByClassName('folium-map')[0].id;
                var map = window[mapElementId];

                map.on('moveend', function() {
                    var center = map.getCenter();
                    new QWebChannel(qt.webChannelTransport, function (channel) {
                        var bridge = channel.objects.bridge;
                        bridge.onMapMoved(center.lat, center.lng);
                    });
                });
                console.log('Map events setup successfully');
            }

            if (typeof L === 'undefined') {
                console.log('Leaflet not loaded yet, retrying...');
                setTimeout(initializeMapEvents, 100);
            } else {
                initializeMapEvents();
            }
        """
        self.webview.page().runJavaScript(script)
        print("Map events setup successfully")

    @pyqtSlot(float, float)
    def onMapMoved(self, lat, lng):
        self.gps_text.setText(f"GPS: {lat}, {lng}")
        script = f"""
                var mapElementId = document.getElementsByClassName('folium-map')[0].id;
                var map = window[mapElementId];
                var marker = L.marker([{lat}, {lng}]).addTo(map);
                """
        self.webview.page().runJavaScript(script)

    def play_video(self):
        self.video_widget.load_video(self.video_path)

    def update_bounding_boxes(self):
        # Example: Generate random bounding boxes
        boxes = [QRect(random.randint(0, 400), random.randint(0, 300), 100, 100)]
        self.set_bounding_boxes(boxes)

    def set_bounding_boxes(self, boxes):
        self.video_widget.setBoundingBoxes(boxes)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.showMaximized()  # Open the window in full size
    sys.exit(app.exec_())
