import math
import sys
import random

from PyQt5 import QtCore
from PyQt5.QtGui import QCursor, QDesktopServices
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage  # install QtWebEngineWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QWidget
from PyQt5.QtCore import QUrl, QRect, QTimer, pyqtSlot, QObject, Qt
import folium

from mainwindow import Ui_MainWindow  # Import the generated UI class
from custom_video_widget import CustomVideoWidget  # Import the custom video widget class

USE_MAPY_CZ = True     # True znamená využití dlaždic z Mapy.cz -> stojí to kredity, False znamená žádné dlaždice


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

        self.prev_angle = 0
        self.camera_gps_coordinates = []
        self.video_widget.set_frame_update_callback(self.update_camera_marker)
        self.video_widget.set_bounding_box_callback(self.bounding_box_clicked)

        self.zpet_na_zacatek.clicked.connect(self.open_video_project)
        self.prehrat.clicked.connect(self.video_widget.pause_unpause)

        # Path to video file
        self.video_path = "D:/bakalarka/360 exports/2023-05-24 S04E03-360 11-55-004 (2)_cropped.mp4"

        self.vehicles = {}  # {id: [type, lat, lon, status]}

        self.zrusit_vozidlo_button.clicked.connect(self.zrusit_vozidlo)

        # -------------------- MAPA --------------------

        self.gps_text.setStyleSheet("color: blue;")
        self.gps_text.setCursor(QCursor(Qt.PointingHandCursor))
        self.gps_text.mousePressEvent = self.open_external_map

        # Create a QWebEngineView widget
        self.webview = QWebEngineView()
        self.webview.setPage(WebEnginePage(self.webview))
        self.mapLayout.addWidget(self.webview)

        # Create a bridge object to communicate between Python and JavaScript
        channel = QWebChannel(self.webview.page())
        channel.registerObject("bridge", self)
        self.webview.page().setWebChannel(channel)

        # Generate Folium map and convert it to HTML
        self.m = folium.Map(location=[50.45570138940419, 14.379894059611189], zoom_start=19, max_zoom=19, min_zoom=16, scrollWheelZoom=False, tiles=None)

        # read the API key from a file
        if USE_MAPY_CZ:
            with open("mapycz_api_key.txt", "r") as file:
                self.API_KEY = file.read().strip()  # TODO: Změnit na vlastní API klíč?
        else:
            self.API_KEY = ""
            print("Využití dlaždic z Mapy.cz není povoleno (USE_MAPY_CZ).")

        # Add custom tile layer from Mapy.cz
        folium.TileLayer(
            tiles='https://api.mapy.cz/v1/maptiles/aerial/256/{z}/{x}/{y}?apikey=' + self.API_KEY,
            attr='<a href="#" onclick="bridge.open_external_link(\'https://api.mapy.cz/copyright\')">&copy; Seznam.cz a.s. a další</a>',
            min_zoom=16,
            max_zoom=20,
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
            f.write("<script src=\"leaflet.rotatedMarker.js\"></script>")   # include the Leaflet.RotatedMarker library

        self.webview.load(QtCore.QUrl.fromLocalFile("/map.html"))

        # Setup map events
        self.webview.loadFinished.connect(self.setup_map_events)
        self.webview.loadFinished.connect(lambda: self.draw_polyline_from_file("D:/bakalarka/PyCharm/bakalarka_ui/programy_parkovani/test_route_gps2.txt"))
        self.webview.loadFinished.connect(lambda: self.read_synced_camera_gps("D:/bakalarka/PyCharm/bakalarka_ui/programy_parkovani/synced_test_route_gps2.txt"))

    def setup_map_events(self):
        script = """
            let markers = [];
            var polyline = null;
            var cameraMarker = null;
            
            var bridge = null;
            new QWebChannel(qt.webChannelTransport, function (channel) {
                    bridge = channel.objects.bridge;
                });
            
            // Add a marker to the map
            function addMarker(id, lat, lng) {
                let marker = L.circleMarker([lat, lng], {
                    radius: 8,
                    color: 'red',
                    fillColor: 'red',
                    fillOpacity: 0.5
                }).addTo(map);
                marker.on('click', function() {
                    bridge.onMarkerClicked(id);
                });
                markers[id] = marker;
            }
            
            // Draw polyline between points
            function drawPolyline(coords) {
                if (polyline) {
                    map.removeLayer(polyline);
                }
                polyline = L.polyline(coords, {color: 'blue'}).addTo(map);
            }
            
            // Update GPS marker position
            function updateCameraMarker(lat, lng, angle) {
                if (cameraMarker) {
                    cameraMarker.setLatLng([lat, lng]);
                    cameraMarker.setRotationAngle(angle - 12);
                } else {
                    // Create custom icon using an SVG file
                    var carIcon = L.icon({
                        iconUrl: 'car-top-view-icon.svg',
                        iconSize: [32, 32],
                        iconAnchor: [16, 8]
                    });
                
                    // Create rotated marker with custom icon
                    cameraMarker = L.marker([lat, lng], {
                        icon: carIcon,
                        rotationAngle: angle - 12
                    }).addTo(map);
                }
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
        script = f"""
                var marker = markers[{self.video_widget.selected_vehicle_id}];
                if (marker) {{
                    marker.setLatLng([%s, %s]);
                }}
                """ % (lat, lng)
        self.webview.page().runJavaScript(script)

    def draw_polyline_from_file(self, filepath):
        gps = []
        with open(filepath, 'r') as file:
            for line in file:
                lat, lng = map(float, line.strip().split(','))
                gps.append([lat, lng])
        script = f"drawPolyline({gps})"
        self.webview.page().runJavaScript(script)

    def read_synced_camera_gps(self, filepath):
        with open(filepath, 'r') as file:
            for line in file:
                lat, lng = map(float, line.strip().split(','))
                self.camera_gps_coordinates.append([lat, lng])

    def update_camera_marker(self, frame_index):
        if frame_index < len(self.camera_gps_coordinates):
            lat, lng = self.camera_gps_coordinates[frame_index]
            if frame_index > 0:
                prev_lat, prev_lng = self.camera_gps_coordinates[frame_index - 1]
                angle = self.calculate_angle(prev_lat, prev_lng, lat, lng)
            else:
                angle = 0
            script = f"updateCameraMarker({lat}, {lng}, {angle})"
            self.webview.page().runJavaScript(script)

    def calculate_angle(self, lat1, lng1, lat2, lng2):
        if lat1 == lat2 and lng1 == lng2:
            return self.prev_angle
        angle = math.degrees(math.atan2(lng2 - lng1, lat2 - lat1))
        self.prev_angle = angle
        return angle

    def open_external_map(self, event):
        # GPS coordinates
        coordinates = self.gps_text.text()
        lat, lon = coordinates.split(", ")

        # Construct the Mapy.cz URL (https://developer.mapy.cz/dalsi-vyuziti-mapy-cz/url-mapy-cz/)
        url = f"https://mapy.cz/fnc/v1/showmap?mapset=aerial&center={lon},{lat}&zoom=20&marker=true"

        # Open the URL in the default web browser
        QDesktopServices.openUrl(QUrl(url))

    @pyqtSlot(str)
    def open_external_link(self, url):
        QDesktopServices.openUrl(QUrl(url))

    @pyqtSlot(int)
    def onMarkerClicked(self, id):
        self.bounding_box_clicked(id)  # na konci volá select_marker
        self.video_widget.seek_video(self.video_widget.highlighted_frames[0])

    def select_marker(self, id):
        set_styles_script = ""
        for key, data in self.vehicles.items():
            vehicle_status = data[3]
            set_styles_script += f"""
                if (markers[{key}]) {{
                    if ('{vehicle_status}' === "done") {{
                        markers[{key}].setStyle({{
                            color: 'green',
                            fillColor: 'green',
                            fillOpacity: 0.6
                        }});
                    }}
                    if ('{vehicle_status}' === "disabled") {{
                        markers[{key}].setStyle({{
                            color: 'lightgray',
                            fillColor: 'lightgray',
                            fillOpacity: 0.2
                        }});
                    }}
                }}
            """

        script = f"""
            for (var i = 0; i < markers.length; i++) {{
                if (markers[i]) {{
                    markers[i].setStyle({{
                        color: 'red',
                        fillColor: 'red',
                        fillOpacity: 0.4
                    }});
                }}
            }}
            {set_styles_script}
            if (markers[{id}]) {{
                markers[{id}].setStyle({{
                    color: 'orange',
                    fillColor: 'orange',
                    fillOpacity: 0.9
                }});
            }} else {{
                console.log('Marker with ID ' + {id} + ' not found');
            }}
            var mapElementId = document.getElementsByClassName('folium-map')[0].id;
            var map = window[mapElementId];
            map.setView(markers[{id}].getLatLng(), map.getZoom());
        """
        self.webview.page().runJavaScript(script)

    def bind_marker_to_move(self, id):
        script = f"""
            var marker = markers[{id}];
            marker.on('drag', function(event) {{
                var lat = event.latlng.lat;
                var lng = event.latlng.lng;
                bridge.onMarkerMoved({id}, lat, lng);
            }});
        """
        self.webview.page().runJavaScript(script)

    # -------------------- VIDEO --------------------

    def open_video_project(self):
        self.video_widget.load_video(self.video_path)
        # načtení všech vozidel
        with open("D:/bakalarka/PyCharm/bakalarka_ui/programy_parkovani/gps_output.txt", 'r') as file:
            for line in file:
                parts = line.strip().split()
                id = int(parts[0])
                type = parts[1]
                lat = float(parts[2])
                lon = float(parts[3])
                if lat == 0 and lon == 0:
                    status = "not_detected"
                else:
                    status = "tbd"
                self.vehicles[id] = [type, lat, lon, status]

        # načtení hotových vozidel
        with open("D:/bakalarka/PyCharm/bakalarka_ui/programy_parkovani/final_output.txt", 'r') as file:
            for line in file:
                parts = line.strip().split()
                id = int(parts[0])
                type = parts[1]
                lat = float(parts[2])
                lon = float(parts[3])
                status = parts[4]
                self.vehicles[id] = [type, lat, lon, status]

        for id, data in self.vehicles.items():
            if data[0] != 0 or data[1] != 0:
                script = f"addMarker({id}, {data[1]}, {data[2]})"
                self.webview.page().runJavaScript(script)

        first_id_tbd = None
        for id, data in self.vehicles.items():
            if data[3] == "tbd":
                first_id_tbd = id
                break
        if first_id_tbd is not None:
            self.bounding_box_clicked(first_id_tbd)
        else:
            for id, data in self.vehicles.items():
                if data[3] != "not_detected":
                    self.bounding_box_clicked(id)
                    break

    def bounding_box_clicked(self, id):
        print(f"Bounding box {id} clicked.")
        frames = []
        with open(f"D:/bakalarka/PyCharm/bakalarka_ui/programy_parkovani/labels/{id}.txt", 'r') as file:
            for line in file:
                parts = line.strip().split()
                frame = int(parts[0])
                frames.append(frame)
        self.video_widget.selected_vehicle_id = id
        self.video_widget.set_highlighted_frames(frames)
        self.select_marker(id)

        if self.vehicles[id][3] == "disabled":
            self.zrusit_vozidlo_button.setText("Obnovit\nvozidlo")
        else:
            self.zrusit_vozidlo_button.setText("Zrušit\nvozidlo")

    # -------------------- TLACITKA --------------------

    def zrusit_vozidlo(self):
        id = self.video_widget.selected_vehicle_id
        if self.vehicles[id][3] == "disabled":
            self.vehicles[id][3] = ""
            self.zrusit_vozidlo_button.setText("Zrušit\nvozidlo")
        else:
            self.vehicles[id][3] = "disabled"
            self.zrusit_vozidlo_button.setText("Obnovit\nvozidlo")
        self.select_marker(id)

        with open("D:/bakalarka/PyCharm/bakalarka_ui/programy_parkovani/final_output.txt", 'w') as file:
            for id, data in self.vehicles.items():
                file.write(f"{id} {data[0]} {data[1]} {data[2]} {data[3]}\n")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.showMaximized()  # Open the window in full size
    sys.exit(app.exec_())
