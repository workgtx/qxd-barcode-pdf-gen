"""

pyBarcode
=========

This package provides a simple way to create standard barcodes.
It needs no external packages to be installed, the barcodes are
created as SVG objects. If Pillow is installed, the barcodes can also be
rendered as images (all formats supported by Pillow).
"""

from barcode.codex import Code128, Code39, Gs1_128, PZN
from barcode.ean import EAN13, EAN14, EAN8, JAN
from barcode.errors import BarcodeNotFoundError
from barcode.isxn import ISBN10, ISBN13, ISSN
from barcode.itf import ITF
from barcode.upc import UPCA
from barcode.version import version  # noqa: F401

__BARCODE_MAP = {
    'ean8': EAN8,
    'ean13': EAN13,
    'ean': EAN13,
    'gtin': EAN14,
    'ean14': EAN14,
    'jan': JAN,
    'upc': UPCA,
    'upca': UPCA,
    'isbn': ISBN13,
    'isbn13': ISBN13,
    'gs1': ISBN13,
    'isbn10': ISBN10,
    'issn': ISSN,
    'code39': Code39,
    'pzn': PZN,
    'code128': Code128,
    'itf': ITF,
    'gs1_128': Gs1_128,
}

PROVIDED_BARCODES = list(__BARCODE_MAP)
PROVIDED_BARCODES.sort()


def get(name, code=None, writer=None, options=None):
    """Helper method for getting a generator or even a generated code.

    :param str name: The name of the type of barcode desired.
    :param str code: The actual information to encode. If this parameter is
        provided, a generated barcode is returned. Otherwise, the barcode class
        is returned.
    :param Writer writer: An alternative writer to use when generating the
        barcode.
    :param dict options: Aditional options to be passed on to the barcode when
        generating.
    """

    options = options or {}
    try:
        barcode = __BARCODE_MAP[name.lower()]
    except KeyError:
        raise BarcodeNotFoundError(
            'The barcode {0!r} you requested is not known.'.format(name)
        )

    if code is not None:
        return barcode(code, writer, **options)
    else:
        return barcode


def get_class(name):
    return get_barcode(name)


def generate(
    name,
    code,
    writer=None,
    output=None,
    writer_options=None,
    text=None,
    pil=False,
):
    options = writer_options or {}
    barcode = get(name, code, writer, options)
    if pil:
        return barcode.render(writer_options, text)
    if isinstance(output, str):
        fullname = barcode.save(output, options, text)
        return fullname
    else:
        barcode.write(output, options, text)


get_barcode = get
get_barcode_class = get_class
