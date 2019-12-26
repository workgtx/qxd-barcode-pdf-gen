#!/usr/bin/python3.6

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.graphics import renderPDF
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFont
from svglib.svglib import svg2rlg
from modules.tqdm import tqdm
from modules import barcode
from configparser import ConfigParser
from io import BytesIO
from sys import argv
from os import listdir
import json


class GetConfiguration:
    """
    Класс устанавливающий глобальные переменные на основании данных конфигурации
    """
    def __init__(self, config):
        self.global_color = dict()
        self.global_pdf_name = str()

        self.doc_width = int()
        self.doc_height = int()
        self.doc_margin = dict()
        self.doc_cell_margin = dict()

        self.mask_add = bool()
        self.mask_color = dict()
        self.mask_border_radius = int()
        self.mask_thickness = float()

        self.cell_width = int()
        self.cell_height = int()
        self.cell_inner_margin = dict()

        self.code_height = int()
        self.code_values = dict()

        self.text_prefix = str()
        self.text_font = str()
        self.text_size = int()
        self.text_adjust_position = dict()

        self._get_config(config)
        self._calculations()

    def _get_config(self, config):
        """"
        Открывает файлы конфигурации и записывает содержимое в аттрибуты инстанса класса
        :param config: имя конфига (без .ini)
        """
        dicts = [
            'margin', 'cell_margin', 'inner_margin',
            'values', 'adjust_position', 'color'
        ]
        booleans = ['add']
        strs = ['prefix', 'font', 'pdf_name']
        floats = ['thickness']

        cfg = ConfigParser()
        cfg.read(f'configs/{config}.ini')

        for section in cfg.sections():
            for option in cfg.options(section):
                if any(option == var for var in booleans):
                    val = cfg.getboolean(section, option)
                elif any(option == var for var in dicts):
                    val = json.loads(cfg.get(section, option))
                elif any(option == var for var in strs):
                    val = cfg.get(section, option)
                elif any(option == var for var in floats):
                    val = cfg.getfloat(section, option)
                else:
                    val = cfg.getint(section, option)
                self.__setattr__(f'{section}_{option}', val)

    def _calculations(self):
        """
        Вычисляет набор дополнительных значений для работы генератора и записывает в аттрибуты
        """
        self.cell_x_pos = self.doc_margin['left']
        self.cell_y_pos = self.doc_height - self.doc_margin['top'] - self.cell_height
        self.code_x_pos = \
            self.doc_margin['left'] + self.doc_cell_margin['x'] + self.cell_inner_margin['left']
        self.code_y_pos = \
            self.doc_height - self.doc_margin['top'] - self.doc_cell_margin['y'] - \
            self.cell_inner_margin['top'] - self.code_height
        self.code_width = \
            self.cell_width - self.cell_inner_margin['left'] - self.cell_inner_margin['right']

        self.text_x_pos = self.code_x_pos
        self.text_y_pos = \
            self.doc_height - self.doc_margin['top'] - self.cell_height + self.cell_inner_margin['bottom']

        self.max_x = \
            (self.doc_width - self.doc_margin['left'] - self.doc_margin['right']) \
            // ((2 * self.doc_cell_margin['x']) + self.cell_width)
        self.max_y = \
            (self.doc_height - self.doc_margin['top'] - self.doc_margin['bottom']) \
            // ((2 * self.doc_cell_margin['y']) + self.cell_height)
        self.x_step = self.cell_width + self.doc_cell_margin['x']
        self.y_step = - self.cell_height + self.doc_cell_margin['y']
        self.text_x_pos = self.text_x_pos + self.text_adjust_position['x']
        self.text_y_pos = self.text_y_pos + self.text_adjust_position['y']


class EyePdfGenerator:
    """
    Основной класс, в котором творится магия
    """
    def __init__(self, config):
        self.cfg = GetConfiguration(config)
        self.canvas = self._make_canvas()
        self._set_canvas_vars()
        self.barcode = bytes()
        self.cell_x_pos = self.cfg.cell_x_pos
        self.cell_y_pos = self.cfg.cell_y_pos
        self.code_x_pos = self.cfg.code_x_pos
        self.code_y_pos = self.cfg.code_y_pos
        self.text_x_pos = self.cfg.text_x_pos
        self.text_y_pos = self.cfg.text_y_pos
        self.left_cells_x = self.cfg.max_x
        self.left_cells_y = self.cfg.max_y
        self.start_id, self.end_id = self.cfg.code_values.values()

    def _make_canvas(self):
        """
        Создаем canvas страницы pdf
        :return: canvas-объект с установленным шрифтом и CMYK
        """
        c = canvas.Canvas(
            f"output/{self.cfg.global_pdf_name}.pdf", pagesize=(
                self.cfg.doc_width * mm, self.cfg.doc_height * mm))
        registerFont(TTFont('MY_FONT', f'fonts/{self.cfg.text_font}'))
        return c

    def _set_canvas_vars(self):
        self.canvas.setFont('MY_FONT', self.cfg.text_size)
        self.canvas.setFillColorCMYK(**self.cfg.global_color)

    def _move_cursor_x(self):
        """
        Сдвигает курсор по оси X вправо для вставки следующей ячейки на правильную позицию
        """
        self.left_cells_x -= 1
        self.code_x_pos += self.cfg.x_step
        self.text_x_pos += self.cfg.x_step

    def _move_cursor_y(self):
        """
        Когда строка ячеек записана перемещает курсор на следующую строку
        и возвращает курсор в крайне правое положение
        :return:
        """
        self.left_cells_x = self.cfg.max_x
        self.left_cells_y -= 1
        self.code_y_pos += self.cfg.y_step
        self.text_y_pos += self.cfg.y_step
        self.code_x_pos = self.cfg.code_x_pos
        self.text_x_pos = self.cfg.text_x_pos

    def _move_to_next_page(self):
        """
        Когда страница заполнена, создается новая и все начинается сначала
        """
        self.code_x_pos = self.cfg.code_x_pos
        self.code_y_pos = self.cfg.code_y_pos
        self.text_x_pos = self.cfg.text_x_pos
        self.text_y_pos = self.cfg.text_y_pos
        self.left_cells_x = self.cfg.max_x
        self.left_cells_y = self.cfg.max_y
        self.canvas.showPage()
        self.canvas.setFont('MY_FONT', 7)

    def return_code(self, id_num):
        """
        Создает баркод с требуемым id
        :param id_num: требуемый id
        """
        fp = BytesIO()
        barcode.generate(
            'code39',
            str(id_num),
            output=fp,
        )
        self.barcode = bytes(fp.getvalue())

    def draw_object(self):
        """
        Отрисовывает svg на странице, предварительно конвертировав его в формат векторной
        графики, который требует reportlab
        """
        drawing = svg2rlg(BytesIO(self.barcode))
        xh, yh = drawing.getBounds()[2:4]
        self.canvas.saveState()
        self.canvas.translate(self.cfg.code_width, self.cfg.code_height)
        drawing.scale(self.cfg.code_width * mm / xh, self.cfg.code_height * mm / yh)
        self.canvas.restoreState()
        renderPDF.draw(drawing, self.canvas, self.code_x_pos * mm, self.code_y_pos * mm)

    def make_pdf(self):
        """
        Итерируется по последовательности и собственно используя функции выше создает pdf-документ
        :return:
        """
        if self.cfg.mask_add:
            mask = EyeMaskPdfGenerator(self.cfg, self.canvas)
            mask.make_mask()
            self.canvas = mask.canvas_return()
            self._set_canvas_vars()

        for x in tqdm(range(self.start_id, self.end_id)):
            self.return_code(x)
            self.draw_object()
            self.canvas.drawString(
                self.text_x_pos*mm, self.text_y_pos*mm, f'{self.cfg.text_prefix[1:-1]}{x}')
            if self.left_cells_x > 1:
                self._move_cursor_x()
            elif self.left_cells_x == 1:
                self._move_cursor_y()
            if self.left_cells_y == 0:
                self._move_to_next_page()
        self.canvas.save()


class EyeMaskPdfGenerator:
    """
    Основной класс, в котором творится магия
    """
    def __init__(self, config, c):
        self.cfg = config
        self.canvas = c
        self.cell_x_pos = self.cfg.cell_x_pos
        self.cell_y_pos = self.cfg.cell_y_pos
        self.left_cells_x = self.cfg.max_x
        self.left_cells_y = self.cfg.max_y
        self.cells_quantity = self.cfg.max_x * self.cfg.max_y
        self.svg = bytes()

    def _move_cursor_x(self):
        """
        Сдвигает курсор по оси X вправо для вставки следующей ячейки на правильную позицию
        """
        self.left_cells_x -= 1
        self.cell_x_pos += self.cfg.x_step

    def _move_cursor_y(self):
        """
        Когда строка ячеек записана перемещает курсор на следующую строку
        и возвращает курсор в крайне правое положение
        :return:
        """
        self.left_cells_x = self.cfg.max_x
        self.left_cells_y -= 1
        self.cell_y_pos += self.cfg.y_step
        self.cell_x_pos = self.cfg.cell_x_pos

    def _move_to_next_page(self):
        """
        Когда страница заполнена, создается новая и все начинается сначала
        """
        self.cell_x_pos = self.cfg.cell_x_pos
        self.cell_y_pos = self.cfg.cell_y_pos
        self.left_cells_x = self.cfg.max_x
        self.left_cells_y = self.cfg.max_y
        self.canvas.showPage()

    def draw_object(self):
        """
        Отрисовывает svg на странице, предварительно конвертировав его в формат векторной
        графики, который требует reportlab
        """
        self.canvas.setLineWidth(self.cfg.mask_thickness)
        self.canvas.setStrokeColorCMYK(*self.cfg.mask_color.values())
        self.canvas.setFillColorCMYK(*self.cfg.mask_color.values())
        self.canvas.roundRect(
            self.cell_x_pos * mm,
            self.cell_y_pos * mm,
            self.cfg.cell_width * mm,
            self.cfg.cell_height * mm,
            radius=self.cfg.mask_border_radius * mm,
            stroke=True,
            fill=False,
        )

    def make_mask(self):
        """
        Итерируется по последовательности и собственно используя функции выше создает pdf-документ
        :return:
        """
        for x in range(self.cells_quantity):
            self.draw_object()
            if self.left_cells_x > 1:
                self._move_cursor_x()
            elif self.left_cells_x == 1:
                self._move_cursor_y()
            if self.left_cells_y == 0:
                self._move_to_next_page()

    def canvas_return(self):
        return self.canvas


def help_me():
    message = "Короче говоря, используется эта штука не просто, а очень просто!\nЕсли ты " \
              "читаешь эти строки, то вероятно тебя постиг успех и ты успешно запустил интерпретатор.\n" \
              "Поздравляю!\n\nОсновные команды:\n  «python3.6 barcodiche.py help»\t\t\t\t Выведет этот мануал\n" \
              "  «python3.6 barcodiche.py list»\t\t\t\t Выведет список доступных конфигураций " \
              "(они лежат в папке «configs/» проекта)\n  «python3.6 barcodiche.py <имя_конфигурации>»\t\t\t" \
              " Применит выбранную конфигурацию (Обрати внимание, что имя "\
              "конфигураци нужно вводить без расширения файла .ini)\n  «python3.6 barcodiche.py credits»\t\t\t\t ЧСВ"
    return message


def get_list_of_configs():
    configs = []

    for filename in listdir('configs'):
        if filename[-4:] == '.ini':
            configs.append(filename)

    print('Короче, найдены вот такие конфигурации:')
    for conf in configs:
        print(f'|-«{conf[:-4]}»')
    print('*--------------------------------------')


def just_credits():
    message = """ \x1b[1;34;40m     Наговнокодил zaphod_beeblebrox для       \x1b[0m \033[91m
 ██████╗ ██╗  ██╗██████╗         ██████╗ ██████╗ 
██╔═══██╗╚██╗██╔╝██╔══██╗        ██╔══██╗╚════██╗
██║   ██║ ╚███╔╝ ██║  ██║        ██║  ██║ █████╔╝
██║▄▄ ██║ ██╔██╗ ██║  ██║        ██║  ██║ ╚═══██╗
╚██████╔╝██╔╝ ██╗██████╔╝███████╗██████╔╝██████╔╝
 ╚══▀▀═╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═════╝ ╚═════╝     \033[0m      
tg: @kurt_simmons mail: work.gtx@gmail.com"""
    return message


if __name__ == '__main__':
    if len(argv) > 1:
        if argv[1] == "list":
            get_list_of_configs()
        elif argv[1] == "help":
            print(help_me())
        elif argv[1] == "credits":
            print(just_credits())
        else:
            EyePdfGenerator(argv[1]).make_pdf()
    else:
        print(help_me())
