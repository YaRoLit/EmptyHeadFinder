import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog as fd
from tkinter import messagebox as mb
import os
from ultralyticsplus import YOLO
import cv2
import threading


def about():
    """
    Вывод информационного окна о приложении.
    Вызывается по кнопке-картинке в левом верхнем углу.
    """
    mb.showinfo("О программе", "Здесь нужно что-то написать...")


def clear():
    """
    Функция очистки форм ввода файлов и пути записи результатов.
    Никаких параметров не принимает и не возвращает.
    """
    global files
    global out_path
    files = ""
    out_path = ""
    filename.delete(0, tk.END)
    pathname.delete(0, tk.END)


def insert_files():
    """
    Функция выбора файлов для расшифровки.
    Ничего не принимает на вход.
    Выбранные файлы записывает в глобальную переменную.
    """
    global files
    global out_path
    clear()
    files = fd.askopenfilenames()
    path, file = os.path.split(files[0])
    out_path = path
    filename.insert(0, files)
    pathname.insert(0, out_path)


def insert_path():
    """
    Функция выбора пути для записи результатов.
    Ничего не принимает на вход.
    Выбранную директорию записывает в глобальную переменную.
    """
    global out_path
    pathname.delete(0, tk.END)
    out_path = fd.askdirectory()
    pathname.insert(0, out_path)


def video_stats(vid_capture):
    """
    Определяем параметры видеофайла:
    количество кадров и скорость воспроизведения (кадр/сек)
    а также размеры кадра, возвращаем эти параметры в виде кортежа
    """
    if vid_capture.isOpened() is False:
        return "Ошибка открытия видеофайла"
    # Чтение fps и количества кадров
    else:
        # Получить информацию о частоте кадров
        # Можно заменить 5 на CAP_PROP_FPS, это перечисления
        fps = vid_capture.get(5)
        print("Фреймов в секунду: ", fps, "FPS")
        # Получить количество кадров
        # Можно заменить 7 на CAP_PROP_FRAME_COUNT, это перечисления
        frame_count = vid_capture.get(7)
        print("Количество кадров: ", frame_count)
        frame_width = int(vid_capture.get(3))
        frame_height = int(vid_capture.get(4))
        return frame_width, frame_height, frame_count


def detect(img, cnt):
    """
    Функция обработки yolo8 для определения наличия на нём людей без каски
    Принимает в качестве аргумента изображение (кадр из видеоряда)
    При обнаружении нужного нам объекта возвращает номер кадра,
    вероятность, координаты ограничивающей рамки
    """
    results = model.predict(img)
    # Перебираем тензоры в целях обнаружения нужных нам объектов
    for box in results[0].boxes:
        # Вытаскиваем значения класса и вероятности распознанных объектов
        cls = int(box.cls)
        # Если нужный нам класс, то возвращаем его номер,
        # вероятность обнаружения объекта, координаты бокса
        if cls == 1:
            return cnt, float(box.conf), box.xyxy.tolist()
        else:
            return False


def show_process(lng=0):
    process = tk.Toplevel()
    process.title("Прогресс выполнения")
    process.geometry("400x50")
    global pb
    pb = ttk.Progressbar(process, length=350, mode="determinate")
    pb.pack()
    stop_button = tk.Button(process, text="Выход",
                            width=15, command=process.destroy)
    stop_button.pack()
    threading.Thread(target=start).start()
    process.mainloop()


def start():
    """
    Запуск модуля ... с выбранными параметрами.
    """
    if not files:
        mb.showerror("Ошибка", "Выберите файлы для расшифровки")
        return

    if not out_path:
        mb.showerror("Ошибка", "Выберите путь для записи результатов")
        return

    # Загрузка модели в соответствии с пользовательским выбором
    # (!!!!тут где-то нужно сделать кэширование моделей)
    global model
    model = YOLO(model_size.get())

    # Установка параметров модели
    model.overrides["conf"] = 0.25  # NMS confidence threshold
    model.overrides["iou"] = 0.45  # NMS IoU threshold
    model.overrides["agnostic_nms"] = False  # NMS class-agnostic
    model.overrides["max_det"] = 1000  # maximum number of detections per image

    for file in files:
        # Захватываем видеозапись в объект
        vid_capture = cv2.VideoCapture(file)
        # Выводим статистику по видеофайлу
        frame_width, frame_height, frame_count = video_stats(vid_capture)
        frame_size = (frame_width, frame_height)
        # Определяем имя для видеофайла-отчёта
        path, filename = os.path.split(file)
        out_file = "out_" + filename
        print(out_file)
        output = cv2.VideoWriter(
            out_path + "/" + out_file,
            cv2.VideoWriter_fourcc(*"XVID"),
            20, frame_size
        )

        # счётчик кадров
        cnt = 0
        # множитель ускорения перемотки видео (х1...х6)
        mlt = process_speed.get()
        # счетчик замедлителя
        abv = 0
        # рассчитываем мультипликатор добавления деления прогресс бара
        rt = (100 / frame_count) / len(files)

        while vid_capture.isOpened():
            # Метод vid_capture.read() возвращают кортеж,
            # первым элементом является логическое значение, а вторым кадр
            ret, frame = vid_capture.read()

            if ret:
                cnt += 1
                pb['value'] += rt
                # Если на видео будет обнаружен объект без каски,
                # с этого момента начинается запись abv количества кадров
                # в выходной видеофайл. Это сделано, чтобы в видео сохранялись
                # не единичные картинки, а полноценный видеоряд
                if abv <= 0:
                    if (cnt % mlt) == 0:
                        obj = detect(frame, cnt)
                        if obj:
                            # Тут указываем, сколько кадров сохранить в файле
                            # с моментa обнаружения нарушения
                            abv = 60
                else:
                    # Выводим видео с нарушениями (если есть соответствующая
                    # галочка в диалоговом окне)
                    if show_vid.get():
                        cv2.imshow("NoHardHat", frame)
                    # Пишем видео в файл
                    output.write(frame)
                    # Уменьшаем счётчик
                    abv -= 1

                key = cv2.waitKey(1)

                if (key == ord("q")) or key == 27:
                    break
            else:
                break

        # Освободить объект захвата видео
        vid_capture.release()
        cv2.destroyAllWindows()

    clear()


# Глобальные переменные (я не нашёл способа обойтись без них)
files = ""
out_path = ""
model = None

# Инициализация основного диалогового окна и его основные параметры
root = tk.Tk()
root.geometry("500x350")
root.title("Зоркий глаз")

# Изображение в левом верхнем углу
img_file = tk.PhotoImage(file="image.png")
tk.Button(root, image=img_file, command=about).grid(
          row=0, column=0, columnspan=2, rowspan=8
        )

# Селектор выбора используемой модели
tk.Label(text="Размер модели:").grid(row=0, column=2, sticky=tk.N, padx=10)
model_size = tk.StringVar()
model_size.set("keremberke/yolov8m-hard-hat-detection")
base = tk.Radiobutton(
    text="Базовая", variable=model_size,
    value="keremberke/yolov8n-hard-hat-detection"
)
small = tk.Radiobutton(
    text="Малая", variable=model_size,
    value="keremberke/yolov8s-hard-hat-detection"
)
medium = tk.Radiobutton(
    text="Средняя", variable=model_size,
    value="keremberke/yolov8m-hard-hat-detection"
)
large = tk.Radiobutton(
    text="Большая", variable=model_size,
    value="keremberke/yolov8l-hard-hat-detection"
)
base.grid(row=1, column=2, sticky=tk.W, padx=10)
small.grid(row=2, column=2, sticky=tk.W, padx=10)
medium.grid(row=3, column=2, sticky=tk.W, padx=10)
large.grid(row=4, column=2, sticky=tk.W, padx=10)

# Селектор выбора типа вывода
tk.Label(text="Обработка моделью:").grid(row=0, column=3, sticky=tk.N, padx=10)
process_speed = tk.IntVar()
process_speed.set(1)
x1 = tk.Radiobutton(text="каждый кадр", variable=process_speed, value=1)
x2 = tk.Radiobutton(text="каждый 2-й", variable=process_speed, value=2)
x4 = tk.Radiobutton(text="каждый 4-й", variable=process_speed, value=4)
x8 = tk.Radiobutton(text="каждый 8-й", variable=process_speed, value=8)
x1.grid(row=1, column=3, sticky=tk.W, padx=10)
x2.grid(row=2, column=3, sticky=tk.W, padx=10)
x4.grid(row=3, column=3, sticky=tk.W, padx=10)
x8.grid(row=4, column=3, sticky=tk.W, padx=10)

# Выбор файлов для расшифровки (метка и кнопка)
tk.Label(text="").grid(row=8, column=0, sticky=tk.W, padx=10, columnspan=4)
tk.Label(text="Выберите файлы для расшифровки:").grid(
    row=9, column=0, sticky=tk.W, padx=10, columnspan=4
)
filename = tk.Entry(width=35)
filename.grid(row=10, column=0, sticky=tk.W, padx=10, columnspan=4)
tk.Button(text="Выбрать файлы", width=15, command=insert_files).grid(
    row=10, column=3, sticky=tk.S, padx=10
)

# Выбор пути вывода результатов
tk.Label(text="Выберите путь вывода результатов:").grid(
    row=12, column=0, sticky=tk.W, padx=10, columnspan=4
)
pathname = tk.Entry(width=35)
pathname.grid(row=13, column=0, sticky=tk.W, padx=10, columnspan=4)
tk.Button(text="Выбрать путь", width=15, command=insert_path).grid(
    row=13, column=3, sticky=tk.S, padx=10
)

# Чекбокс типа отображения процесса расшифровки
tk.Label(text="").grid(row=14, column=0, sticky=tk.W, padx=10, columnspan=4)
show_vid = tk.BooleanVar()
show_vid.set("False")
show_vid_check = tk.Checkbutton(
    root,
    text="Показывать видео нарушений",
    variable=show_vid,
    onvalue="True",
    offvalue="False",
)
show_vid_check.grid(row=15, column=0, sticky=tk.W, padx=10, columnspan=4)

# Главная красная кнопка
start_button = tk.Button(text="Старт обработки",
                         width=15, command=show_process)
start_button["bg"] = "#fa4400"
start_button.grid(row=15, column=3, sticky=tk.S, padx=10)

root.mainloop()
