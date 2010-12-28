#!/usr/bin/env python
import glob, os

#make trigger_inact.xpm from trigger.xpm
os.system(r'''sed -e 's/E/7/g' < trigger.xpm | sed -e 's/F/8/g' >trigger_inact.xpm''')

for infile in glob.glob('*.xpm'):
    file, ext = os.path.splitext(infile)
    print infile + '->' + file + '.png'

    # '#110110' is transparent marker. No use this color in xpm files.
    os.system(r'''sed -e '/^\/\*$/,/^\*\/$/d' <%s  | sed -e '/^$/d' | sed -e 's/None/#110110/' | xpmtoppm | pnmtopng -transparent "#110110">%s.png''' % (infile, file))
