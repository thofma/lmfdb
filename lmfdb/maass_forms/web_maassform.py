from lmfdb import db
from lmfdb.utils import display_knowl
from flask import url_for
from sage.all import ZZ

def th_wrap(kwl, title):
    return '    <th>%s</th>' % display_knowl(kwl, title=title)
def td_wrapl(val):
    return '    <td align="left">%s</td>' % val
def td_wrapc(val):
    return '    <td align="center">%s</td>' % val
def td_wrapr(val):
    return '    <td align="right">%s</td>' % val

def parity_text(val):
    return 'odd' if val == -1 else 'even'

class WebMaassForm(object):
    def __init__(self, data):
        self.__dict__.update(data)
        self._data = data

    @staticmethod
    def by_label(label):
        try:
            data = db.maass_newforms.lookup(label)
        except AttributeError:
            raise KeyError("Maass newform %s not found in database."%(label))
        return WebMaassForm(data)

    @property
    def label(self):
        return self.maass_id #TODO: we should revisit this at some point

    @property
    def title(self):
        return r"Maass form on \(\Gamma_0(%d)\) with \(R=%s\)"%(self.level,self.spectral_parameter)

    @property
    def properties(self):
        return [('Level', str(self.level)),
                ('Weight', str(self.weight)),
                ('Character', self.character_label),
                ('Symmetry', self.symmetry_pretty),
                ('Fricke eigenvalue', str(self.fricke_eigenvalue)),
                ]

    @property
    def factored_level(self):
        return ' = ' + ZZ(self.level).factor()._latex_()

    @property
    def character_label(self):
        return "%d.%d"%(self.level, self.conrey_index)

    @property
    def character_link(self):
        return display_knowl('character.dirichlet.data', title=self.character_label, kwargs={'label':self.character_label})

    @property
    def symmetry_pretty(self):
        return "even" if self.symmetry == 1 else ("odd" if self.symmetry == -1 else "")

    @property
    def bread(self):
        return [('Modular forms', url_for('modular_forms')),
                ('Maass', url_for(".index")),
                ("Weight %d"%(self.weight), url_for(".by_weight",weight=self.weight)),
                ("Level %d"%(self.level), url_for(".by_level",weight=self.weight,level=self.level)),
                ("Character %s"%(self.character_label), url_for("by_character",weight=self.weight,level=self.level,conrey_index=self.conrey_index)),
                ]

    @property
    def downloads(self):
        return [("Coefficients to text", url_for (".download_coefficients", label=self.label)),
                ("All stored data to text", url_for (".download_all_data", label=self.label)),
                ]

    @property
    def friends(self):
        return [("L-function", "/L" + url_for(".by_lavel"))]

    def coefficient_table(self,rows=10, cols=10):
        if not self.coefficients:
            return ""
        n = len(self.coefficients)
        assert rows > 0 and cols > 0
        table = ['<table class="ntdata">']
        if (rows-1)*cols <= n:
            rows = (n // cols) + (1 if (n%cols) else 0)
        for i in range(rows):
            table.append('<tr>')
            for j in range(cols):
                if i*cols+j > n:
                    break
                table.append(td_wrapl(r"\(a_%d=%.9f\)"%(i*cols+j+1,self.coefficients[i*cols+j])))
            table.append('</tr>')
        table.append('</table>')
        if rows*cols < n:
            table.append('<p>Showing %d of %d coefficients available</p>' % (rows*cols,n))
        return '\n'.join(table)
