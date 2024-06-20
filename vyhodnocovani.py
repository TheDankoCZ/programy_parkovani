import sys
import random

from PyQt5 import QtCore
from PyQt5.QtGui import QCursor, QDesktopServices
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage  # install QtWebEngineWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, QRect, QTimer, pyqtSlot, QObject, Qt
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
        max_height = 400
        self.video_widget = CustomVideoWidget(max_width=max_width, max_height=max_height, labels_dir="D:/bakalarka/PyCharm/bakalarka_ui/programy_parkovani/labels")
        self.videoLayout.addWidget(self.video_widget)

        self.gps_text.setStyleSheet("color: blue;")
        self.gps_text.setCursor(QCursor(Qt.PointingHandCursor))
        self.gps_text.mousePressEvent = self.open_external_map

        self.zpet_na_zacatek.clicked.connect(self.play_video)
        self.prehrat.clicked.connect(self.video_widget.pause_unpause)

        # Path to video file
        self.video_path = "D:/bakalarka/360 exports/2023-05-24 S04E03-360 11-55-004 (2)_cropped.mp4"

        # Create a QWebEngineView widget
        self.webview = QWebEngineView()
        self.webview.setPage(WebEnginePage(self.webview))
        self.mapLayout.addWidget(self.webview)

        # Create a bridge object to communicate between Python and JavaScript
        channel = QWebChannel(self.webview.page())
        channel.registerObject("bridge", self)
        self.webview.page().setWebChannel(channel)

        # Generate Folium map and convert it to HTML
        self.m = folium.Map(location=[50.77899, 14.21680], zoom_start=19, max_zoom=19, min_zoom=16, scrollWheelZoom=False, tiles=None)

        # read the API key from a file
        with open("mapycz_api_key.txt", "r") as file:
            self.API_KEY = file.read().strip()  # TODO: Replace with your own API key!

        # Add custom tile layer from Mapy.cz
        folium.TileLayer(
            tiles='https://api.mapy.cz/v1/maptiles/aerial/256/{z}/{x}/{y}?apikey=' + self.API_KEY,
            attr='<a href="#" onclick="bridge.open_external_link(\'https://api.mapy.cz/copyright\')">&copy; Seznam.cz a.s. a další</a>',
            min_zoom=16,
            max_zoom=19,
            name='Mapy.cz',
            overlay=False,
            control=True
        ).add_to(self.m)

        # Save the map as an HTML file
        self.m.save("map.html")

        # Modify the HTML to include the custom logo control
        with open("map.html", "r") as file:
            map_html = file.read()

        logo_html = """
                <style>
                .logo-control {
                    position: absolute;
                    bottom: 10px;
                    left: 10px;
                    z-index: 1000;
                }
                </style>
                <div class="logo-control">
                    <a href="#" onclick="bridge.open_external_link('https://mapy.cz/')">
                        <img src="https://api.mapy.cz/img/api/logo.svg" alt="Mapy.cz Logo">
                    </a>
                </div>
                </body>
                """

        map_html = map_html.replace("</body>", logo_html)

        with open("map.html", "w") as file:
            file.write(map_html)

        # Append to the html file
        with open("map.html", "a") as f:
            f.write("<script src=\"qrc:///qtwebchannel/qwebchannel.js\"></script>")

        self.webview.load(QtCore.QUrl.fromLocalFile("/map.html"))

        # Setup map events
        self.webview.loadFinished.connect(self.setup_map_events)
        self.webview.loadFinished.connect(self.add_markers)

    def setup_map_events(self):
        script = """
            let markers = [];
            
            var bridge = null;
            new QWebChannel(qt.webChannelTransport, function (channel) {
                    bridge = channel.objects.bridge;
                });
            
            // Add a marker to the map
            function addMarker(id, lat, lng) {
                let marker = L.marker([lat, lng], popup=id.toString()).addTo(map);
                markers[id] = marker;
            }
        
            var mapElementId = document.getElementsByClassName('folium-map')[0].id;
            var map = window[mapElementId];
            
            // Attach event listeners to continuously update marker position while moving the map
            map.on('movestart', function() {
                var center = map.getCenter();
                bridge.onMapMoving(center.lat, center.lng);
            });
            
            map.on('move', function() {
                var center = map.getCenter();
                bridge.onMapMoving(center.lat, center.lng);
            });
            
            console.log('Map events setup successfully');
        """
        self.webview.page().runJavaScript(script)
        print("Map events setup successfully")

    @pyqtSlot(float, float)
    def onMapMoving(self, lat, lng):
        self.gps_text.setText(f"{lat}, {lng}")
        script = """
                var mapElementId = document.getElementsByClassName('folium-map')[0].id;
                var map = window[mapElementId];
                var marker = markers[0];
                if (marker) {
                    marker.setLatLng([%s, %s]);
                }
                """ % (lat, lng)
        self.webview.page().runJavaScript(script)

    def add_markers(self):
        script = """
            addMarker(0, 50.77899, 14.21680);
            """
        self.webview.page().runJavaScript(script)

    def open_external_map(self, event):
        # GPS coordinates
        coordinates = self.gps_text.text()
        lat, lon = coordinates.split(", ")

        # Construct the Mapy.cz panorama URL
        url = f"https://mapy.cz/fnc/v1/showmap?mapset=aerial&center={lon},{lat}&zoom=20&marker=true"

        # Open the URL in the default web browser
        QDesktopServices.openUrl(QUrl(url))

    @pyqtSlot(str)
    def open_external_link(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def play_video(self):
        self.video_widget.load_video(self.video_path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.showMaximized()  # Open the window in full size
    sys.exit(app.exec_())
