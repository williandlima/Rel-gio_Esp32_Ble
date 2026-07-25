# Fonte de blocos para o Modo Letreiro "ampliado": o texto inteiro vira uma
# tira contínua de pixels (4 linhas), que quem chama rola pela tela igual ao
# Modo Rolagem normal — só que em resolução de pixel em vez de caractere.
#
# Cada glifo é uma matriz de 4 linhas x 5 colunas ("#" = aceso). Na hora de
# desenhar, cada coluna vira `scale` colunas do display, então com scale=4 um
# único caractere ocupa exatamente as 20 colunas do display.
#
# O "pixel" aceso NÃO usa nenhuma posição da ROM de caracteres: o bloco cheio
# é gravado na CGRAM pelo próprio firmware (ver BLOCK_BITMAP e
# LCD4Bit.create_char). Depender da ROM era frágil — a posição 0xFF só é um
# bloco sólido em parte das variantes do controlador, e nas demais o letreiro
# saía desenhado com um símbolo qualquer, ilegível.

VERSION = "bigfont v3 (tira continua de pixels, para rolar como as demais)"

# Índice do caractere customizado usado como "pixel aceso". Evita o índice 0
# para não trafegar byte nulo nas strings.
BLOCK_INDEX = 1
BLOCK_BITMAP = (0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F)

_ON = chr(BLOCK_INDEX)
_OFF = " "

GLYPH_COLS = 5
GLYPH_ROWS = 4

_GLYPHS = {
    " ": ("     ", "     ", "     ", "     "),
    "A": (".###.", "#...#", "#####", "#...#"),
    "B": ("####.", "#..#.", "####.", "####."),
    "C": (".####", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "####.", "#####"),
    "F": ("#####", "#....", "####.", "#...."),
    "G": (".####", "#....", "#..##", ".####"),
    "H": ("#...#", "#####", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "#..#.", ".##.."),
    "K": ("#..#.", "###..", "###..", "#..#."),
    "L": ("#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#...#"),
    "N": ("##..#", "#.#.#", "#.#.#", "#..##"),
    "O": (".###.", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "####.", "#...."),
    "Q": (".###.", "#...#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "####.", "#..##"),
    "S": (".####", "##...", "...##", "####."),
    "T": ("#####", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#.#.#", "#.#.#", ".#.#."),
    "X": ("#...#", ".#.#.", ".#.#.", "#...#"),
    "Y": ("#...#", ".#.#.", "..#..", "..#.."),
    "Z": ("#####", "..##.", ".##..", "#####"),
    "0": (".###.", "#..##", "##..#", ".###."),
    "1": ("..#..", ".##..", "..#..", ".###."),
    "2": ("####.", "...##", ".##..", "#####"),
    "3": ("####.", "..##.", "...##", "####."),
    "4": ("#..#.", "#..#.", "#####", "...#."),
    "5": ("#####", "####.", "...##", "####."),
    "6": (".###.", "#....", "####.", ".###."),
    "7": ("#####", "...#.", "..#..", ".#..."),
    "8": (".###.", "#...#", ".###.", ".###."),
    "9": (".###.", "####.", "...#.", ".###."),
    ".": (".....", ".....", ".....", "..##."),
    ",": (".....", ".....", "..##.", ".##.."),
    ":": (".....", "..#..", ".....", "..#.."),
    ";": (".....", "..#..", ".....", ".##.."),
    "!": ("..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "...#.", "..#..", "..#.."),
    "-": (".....", ".....", "#####", "....."),
    "_": (".....", ".....", ".....", "#####"),
    "=": (".....", "#####", ".....", "#####"),
    "+": ("..#..", "#####", "..#..", "....."),
    "*": (".#.#.", "..#..", ".#.#.", "....."),
    "/": ("....#", "...#.", "..#..", ".#..."),
    "\\": ("#....", ".#...", "..#..", "...#."),
    "(": ("..##.", ".#...", ".#...", "..##."),
    ")": (".##..", "...#.", "...#.", ".##.."),
    "[": ("..##.", "..#..", "..#..", "..##."),
    "]": (".##..", "..#..", "..#..", ".##.."),
    "'": ("..#..", "..#..", ".....", "....."),
    '"': (".#.#.", ".#.#.", ".....", "....."),
    "<": ("...#.", "..#..", ".#...", "..##."),
    ">": (".#...", "..#..", "...#.", "##..."),
    "%": ("#...#", "...#.", "..#..", "#...#"),
    "&": (".##..", "###..", "#..##", ".####"),
    "@": (".###.", "#.###", "#....", ".###."),
    "$": (".####", "###..", "..###", "####."),
    "#": (".#.#.", "#####", ".#.#.", "#####"),
}

_FALLBACK = _GLYPHS["?"]


def has_glyph(ch):
    return ch.upper() in _GLYPHS


def render_strip(text, rows=GLYPH_ROWS, scale=4, gap=1):
    """Monta `rows` strings com o texto inteiro concatenado em pixels
    (um caractere colado no outro, com `gap` colunas em branco de
    respiro entre eles). O resultado NÃO tem o tamanho do display — quem
    chama recorta uma janela de `cols` colunas e desliza essa janela para
    fazer a rolagem, exatamente como o Modo Rolagem faz com o texto
    normal (ver clock_app._render_show)."""
    strips = [""] * rows
    gap_blank = _OFF * (gap * scale)
    for ch in text:
        glyph = _GLYPHS.get(ch.upper(), _FALLBACK)
        for row in range(rows):
            bits = glyph[row] if row < len(glyph) else _OFF * GLYPH_COLS
            expanded = "".join((_ON if c == "#" else _OFF) * scale for c in bits)
            strips[row] += expanded + gap_blank
    return strips
