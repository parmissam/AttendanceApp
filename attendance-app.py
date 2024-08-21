import sys
import sqlite3, cv2, shutil
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer
import time, datetime, os, base64, dlib, io,face_recognition, tempfile
import numpy as np
from PIL import Image
from persiantools.jdatetime import JalaliDateTime
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QDialog, QLabel, QLineEdit, QVBoxLayout, QMessageBox, QFileDialog, QWidget, QInputDialog
import pandas as pd
xml_path = r"C:\Users\MJPARSIJANI\Desktop\Hozourghyab\images\haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(xml_path)
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Main Window")
        self.setGeometry(100, 100, 400, 300)

        self.define_member_button = QPushButton("تعریف عضو")
        self.check_face_button = QPushButton("چک چهره")
        self.check_fingerprint_button = QPushButton("چک اثر انگشت")
        self.delete_member_button = QPushButton("حذف عضو")
        self.export_excel_button = QPushButton("خروجی به اکسل")

        self.define_member_button.clicked.connect(self.show_define_member_dialog)
        self.check_face_button.clicked.connect(self.toggle_face_check) 
        self.delete_member_button.clicked.connect(self.delete_member)
        self.export_excel_button.clicked.connect(self.export_to_excel)
        self.check_fingerprint_button.clicked.connect(self.check_fingerprint)

        layout = QVBoxLayout()
        layout.addWidget(self.define_member_button)
        layout.addWidget(self.check_face_button)
        layout.addWidget(self.delete_member_button)
        layout.addWidget(self.export_excel_button)
        layout.addWidget(self.check_fingerprint_button)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        self.is_face_check_running = False 

    def toggle_face_check(self):
        if self.is_face_check_running:
            self.stop_face_check()
        else:
            self.start_face_check()

    def start_face_check(self):
        self.is_face_check_running = True
        self.check_face_button.setText("توقف چک چهره")  
        self.run_face_check()

    def stop_face_check(self):
        self.is_face_check_running = False
        self.check_face_button.setText("چک اثر انگشت یا چهره")  

    def show_define_member_dialog(self):
        if hasattr(self, 'member_definition_dialog') and self.member_definition_dialog.isVisible():
            self.member_definition_dialog.close()
            return

        self.member_definition_dialog = MemberDefinitionDialog()
        self.member_definition_dialog.show()

    def run_face_check(self):
        try:
            video_capture = cv2.VideoCapture(0)
            fps_limit = 10  
            frame_interval = 0.25 / fps_limit
            last_frame_time = time.time()

            conn = sqlite3.connect('../database.db')
            cursor = conn.cursor()

            known_images = []  
            known_encodings = []  
            known_nationals = []  
            known_names = []  
            known_last_names = [] 

            cursor.execute('SELECT national_code, name, last_name, image FROM table1')
            rows = cursor.fetchall()

            if not rows:
                QMessageBox.warning(self, "خطا", "دیتابیس خالی است.")
                return

            for national_code, name, last_name, image_data in rows:
                image_blob = io.BytesIO(image_data)
                pil_image = Image.open(image_blob)
                numpy_array = np.array(pil_image)
                face_encoding = face_recognition.face_encodings(numpy_array)[0] 
                known_images.append(numpy_array)
                known_encodings.append(face_encoding)
                known_nationals.append(national_code)
                known_names.append(name)
                known_last_names.append(last_name)

            while self.is_face_check_running:
                ret, frame = video_capture.read()

                face_locations = face_recognition.face_locations(frame)
                face_encodings = face_recognition.face_encodings(frame, face_locations)

                for face_encoding in face_encodings:
                    matches = face_recognition.compare_faces(known_encodings, face_encoding)

                    for i, match in enumerate(matches):
                        if match:
                            matched_national = known_nationals[i]
                            matched_name = known_names[i]
                            matched_last_name = known_last_names[i]

                            current_time = time.strftime('%H:%M:%S')

                            current_jalali_datetime = JalaliDateTime.today()
                            current_date = current_jalali_datetime.strftime("%Y/%m/%d")

                            cursor.execute("SELECT * FROM table2 WHERE national_code = ? AND date = ?",
                                           (matched_national, current_date))
                            existing_record = cursor.fetchone()

                            if existing_record:
                                cursor.execute("UPDATE table2 SET khoroj = ? WHERE national_code = ? AND date = ?",
                                               (current_time, matched_national, current_date))
                                conn.commit()
                            else:
                                cursor.execute(
                                    "INSERT INTO table2 (vorod, khoroj, date, name, last_name, national_code) VALUES (?, ?, ?, ?, ?, ?)",
                                    (current_time, None, current_date, matched_name, matched_last_name,
                                     matched_national))
                                conn.commit()

                            if matched_national:
                                top, right, bottom, left = face_recognition.face_locations(frame)[0]
                                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                                font = cv2.FONT_HERSHEY_DUPLEX
                                cv2.putText(frame, f"{matched_national} your attendance submitted",
                                            (left + 6, bottom - 6),
                                            font, 0.5, (255, 255, 255), 1)


                cv2.imshow('Video', frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):

            video_capture.release()
            cv2.destroyAllWindows()

            conn.close()

            if self.is_face_check_running:
                self.run_face_check()

        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در تشخیص چهره: {str(e)}")
            return

    def delete_member(self):
        try:
            national_code, ok = QInputDialog.getText(self, "حذف عضو", "لطفاً کد ملی عضو را وارد کنید:")
            if ok:
                conn = sqlite3.connect('../database.db')
                cursor = conn.cursor()

                cursor.execute("SELECT national_code FROM table1 WHERE national_code = ?", (national_code,))
                existing_member = cursor.fetchone()

                if existing_member:
                    cursor.execute("DELETE FROM table1 WHERE national_code = ?", (national_code,))
                    conn.commit()

                    cursor.execute("DELETE FROM table2 WHERE national_code = ?", (national_code,))
                    conn.commit()

                    conn.close()

                    QMessageBox.information(self, "حذف عضو", "عضو با موفقیت حذف شد.")
                else:
                    QMessageBox.warning(self, "خطا", "کد ملی وارد شده یافت نشد.")
                    conn.close()
        except Exception as e:
            QMessageBox.critical(self, "خطا", "خطا در حذف عضو: " + str(e))
    def check_fingerprint(self):
        return
    def export_to_excel(self):
        try:
            conn = sqlite3.connect('../database.db')
            query = "SELECT * FROM table2"
            df = pd.read_sql_query(query, conn)
            conn.close()

            desktop_path = os.path.expanduser("~/Desktop")
            excel_file_path = os.path.join(desktop_path, "table2_data.xlsx")

            df.to_excel(excel_file_path, index=False)

            QMessageBox.information(self, "خروجی به اکسل", "اطلاعات با موفقیت به فایل Excel خروجی داده شد.")
        except Exception as e:
            QMessageBox.critical(self, "خطا", "خطا در صدور به فایل Excel: " + str(e))

class MemberDefinitionDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Define Members")
        self.layout = QVBoxLayout()

        self.face_image = None

        self.name_input = QLineEdit()
        self.last_name_input = QLineEdit()
        self.national_code_input = QLineEdit()

        self.image_label = QLabel("No Image")
        self.submit_button = QPushButton("ثبت")
        self.capture_button = QPushButton("روشن کردن وبکم")

        self.capture_button.clicked.connect(self.toggle_camera)
        self.submit_button.clicked.connect(self.submit_data)

        self.layout.addWidget(QLabel("نام:"))
        self.layout.addWidget(self.name_input)
        self.layout.addWidget(QLabel("نام خانوادگی:"))
        self.layout.addWidget(self.last_name_input)
        self.layout.addWidget(QLabel("کد ملی:"))
        self.layout.addWidget(self.national_code_input)
        self.layout.addWidget(self.image_label)
        self.layout.addWidget(self.capture_button)
        self.layout.addWidget(self.submit_button)

        self.setLayout(self.layout)

        self.cap = None
        self.is_camera_active = False

        self.camera_timer = QTimer(self) 
        self.camera_timer.timeout.connect(self.update_camera_feed)

        self.finished.connect(self.stop_camera)

    def toggle_camera(self):
        if self.is_camera_active:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        try:
            self.cap = cv2.VideoCapture(0)  
            if not self.cap.isOpened():
                raise Exception("Unable to access the camera.")

            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

            self.is_camera_active = True
            self.capture_button.setText("متوقف کردن وبکم")

            self.camera_timer.start(100) 

            while self.is_camera_active:
                ret, frame = self.cap.read()
                if not ret:
                    raise Exception("Failed to capture frame.")

                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    face = frame[y:y + h, x:x + w]

                    
                    self.face_image = face

                    self.image_label.setText("تصویر با موفقیت تایید و ثبت شد. برای ادامه دکمه ثبت را فشار دهید.")
                    self.submit_button.setEnabled(True)

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                q_image = QImage(frame.data, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_image)
                self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio))

                QApplication.processEvents()

        except Exception as e:
            QMessageBox.critical(self, "خطا", "خطا در روشن کردن دوربین: " + str(e))
            self.stop_camera()

    def stop_camera(self):
        try:
            if self.cap is not None and self.cap.isOpened():
                self.cap.release()
            if self.camera_timer.isActive():
                self.camera_timer.stop()
            self.is_camera_active = False
            self.capture_button.setText("روشن کردن وبکم")
            self.image_label.setText("No Image")
        except Exception as e:
            print("Error stopping camera:", str(e))

    def update_camera_feed(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            q_image = QImage(frame.data, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)
            self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio))

    def submit_data(self):
        try:
            if self.name_input.text() and self.last_name_input.text() and self.face_image is not None:
                national_code = self.national_code_input.text()
                if not national_code.isdigit() or len(national_code) != 10:
                    QMessageBox.warning(self, "خطا", "لطفاً کد ملی را به صورت یک عدد 10 رقمی وارد کنید.")
                    return
                try:
                    image_filename = "face_image.jpg"
                    cv2.imwrite(image_filename, self.face_image)

                    temp_dir = tempfile.mkdtemp()
                    temp_image_path = os.path.join(temp_dir, "face_image.jpg")

                    cv2.imwrite(temp_image_path, self.face_image)

                    with open(temp_image_path, "rb") as image_file:
                        image_data = image_file.read()

                    conn = sqlite3.connect('../database.db')
                    cursor = conn.cursor()

                    cursor.execute("INSERT INTO table1 (name, last_name, national_code, image) VALUES (?, ?, ?, ?)",
                                   (self.name_input.text(), self.last_name_input.text(), self.national_code_input.text(),
                                    image_data))
                    conn.commit()
                    conn.close()

                    QMessageBox.information(self, "ثبت اطلاعات", "اطلاعات با موفقیت ثبت شد.")
                except Exception as e:
                    QMessageBox.critical(self, "خطا", "خطا در ثبت اطلاعات: " + str(e))
                finally:
                    self.name_input.clear()
                    self.last_name_input.clear()
                    self.national_code_input.clear()
                    self.image_label.clear()

                    self.face_image = None

                    self.submit_button.setEnabled(False)

            else:
                QMessageBox.warning(self, "خطا", "لطفا تمام اطلاعات را وارد کنید و ابتدا عکس چهره خود را ذخیره نمایید.")
        finally:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)

def create_tables():
    conn = sqlite3.connect('../database.db')
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS table1 (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    last_name TEXT,
                    national_code int,
                    image BLOB)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS table2 (
                    id INTEGER PRIMARY KEY,
                    vorod TIME,
                    khoroj TIME,
                    date DATE,
                    name TEXT,
                    last_name TEXT,
                    national_code INT)''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())
