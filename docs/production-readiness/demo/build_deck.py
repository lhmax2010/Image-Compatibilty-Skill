#!/usr/bin/env python3
"""Generate and structural-check the English HQ deck without external dependencies."""
import argparse
from dataclasses import dataclass
from html import escape
from pathlib import Path, PurePosixPath
import posixpath
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
TYPES = 'http://schemas.openxmlformats.org/package/2006/content-types'
DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
NS = f'xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{REL}"'
EMU = 9525
WIDTH, HEIGHT = 1280, 720
PALETTE = {
    'bg':'0B1521', 'panel':'142536', 'panel2':'1A2D3D', 'ink':'F5F9FC', 'muted':'B5C6D3',
    'mint':'7DDFC2', 'coral':'FFAA9B', 'gold':'F5D589', 'line':'254051',
}


@dataclass
class Box:
    x: int
    y: int
    width: int
    height: int
    value: str = ''
    fill: str | None = None
    color: str = 'ink'
    size: int = 22
    bold: bool = False
    font: str = 'Aptos'


def B(x,y,width,height,value='',**style):
    return Box(x,y,width,height,value,**style)


def heading(label, title, subtitle=None):
    rows = [B(70,53,1100,24,label,color='mint',size=14,bold=True),
            B(70,91,1120,78,title,size=39,bold=True)]
    if subtitle:
        rows.append(B(72,173,1110,62,subtitle,size=20,color='muted'))
    return rows


def footer():
    return [B(70,656,1140,2,fill='line'),
            B(70,674,1080,22,'TIZEN IMAGE COMPATIBILITY  /  HEADQUARTERS DEMO',color='muted',size=11)]


def panel(x,y,w,h,top,headline,body,accent='mint'):
    return [B(x,y,w,h,fill='panel'),B(x+20,y+17,w-40,23,top,color=accent,size=13,bold=True),
            B(x+20,y+52,w-40,48,headline,size=26,bold=True),
            B(x+20,y+108,w-40,h-118,body,size=18,color='muted')]


def slide_content():
    slides = [
        [B(70,66,900,30,'TIZEN DEVELOPER TOOLING',color='mint',size=15,bold=True),
         B(70,141,1130,250,'AI-assisted Tizen\nGCC-to-LLVM Image\nCompatibility Validation',size=56,bold=True),
         B(72,430,940,92,'Find binary-interface breaks before consumers encounter them.',size=26,color='muted'),
         B(70,550,470,65,fill='panel'),
         B(91,570,430,26,'OFFLINE DEMO  /  SYNTHETIC RPMs',size=16,color='mint',bold=True)],
        [*heading('WORKFLOW','One request, one reproducible run','The agent provides input and intent. The engine owns the evidence and decisions.'),
         *panel(70,270,362,285,'INPUT','Describe inputs','Baseline and candidate RPM directories, output path and the export-validation objective.'),
         *panel(459,270,362,285,'ENGINE','Compare ELF','Read archive metadata, extract payloads, inspect ELF and symbols, then compute scoped findings.'),
         *panel(848,270,362,285,'REPORT','Review evidence','Start with the small run summary. Open the relevant package, library, symbol and original evidence.')],
        [*heading('LIVE SYNTHETIC INPUT','Four RPMs. Four ELF payloads.','Two packages per side, with independent archive and object identities.'),
         *panel(70,250,552,280,'BASELINE','Version 1-1 packages','demo-codec and demo-client\nTwo extracted RPMs · two ELF objects\nSeven export observations · one import\nProvider exposes legacy_export@@DEMO_1.'),
         *panel(648,250,562,280,'CANDIDATE','Version 2-1 packages','demo-codec and demo-client\nTwo extracted RPMs · two ELF objects\nSeven export observations · one import\nProvider removes legacy_export@@DEMO_1.'),
         B(70,572,1110,44,'ELF content identifies both objects. Their payload filenames have no .so suffix.',color='mint',size=17)],
        [*heading('SYMBOL DETAILS','Find the change that matters','Follow the demo-codec package ID from the ELF summary into the symbol CSV.'),
         B(70,245,1140,38,fill='panel2'),B(88,253,282,26,'INTERFACE',size=14,bold=True,color='mint'),
         B(417,253,482,26,'BASELINE → CANDIDATE',size=14,bold=True,color='mint'),
         B(933,253,250,26,'OBSERVATION',size=14,bold=True,color='mint')],
        [*heading('CONSUMER AND PROVIDER','Trace a potential impact','Use the versioned import to locate the affected provider contract.'),
         *panel(70,253,552,268,'CONSUMER · demo-client','legacy_export@DEMO_1','The import persists on both sides. ELF version requirements name libdemo-codec.so.1.'),
         *panel(648,253,562,268,'PROVIDER · demo-codec','legacy_export@@DEMO_1','The baseline export is absent from the candidate provider’s complete inventory.','coral'),
         B(70,552,1140,75,'Open the original Finding and its evidence. Installed loader resolution remains UNKNOWN.',size=19,color='gold')],
        [*heading('READ THE REPORT','Completion and compatibility are separate','Four independent statements describe one run.'),
         *panel(70,249,552,165,'EXECUTION','COMPLETE','The required collectors finished.'),
         *panel(648,249,562,165,'EXPORT OBJECTIVE','COMPLETE','Both scoped sides were analyzed.'),
         *panel(70,437,552,165,'COMPATIBILITY','INCOMPATIBLE','Confirmed static contract breaks.','coral'),
         *panel(648,437,562,165,'COVERAGE','PARTIAL','2 / 2 ELF tables per side. Loader context is unknown.','gold')],
        [*heading('HISTORICAL DEVICE OBSERVATION','What the Raspberry Pi verified','Prior SR LLVM headed test on Raspberry Pi 4, ARMv7l.'),
         *panel(70,269,552,266,'OBSERVED','4 / 4 sample executions','Four frozen C/C++ probes exited 0 with expected stdout, verified bytes and independent cleanup.'),
         *panel(648,269,562,266,'STILL UNVERIFIED','0 / 8 headless matrix','A matching VD headed reference and formally scoped dual-image execution remain open.','gold'),
         B(70,572,1100,59,'Today’s synthetic demo runs offline without accessing the device.',color='muted',size=18)],
        [*heading('RERUN THE DEMO','Take the workflow to your own machine','Preflight on an authorized Linux host, then use a new output directory.'),
         B(70,252,1140,100,fill='panel'),
         B(93,270,1080,33,'python3 run_demo.py --preflight',font='Consolas',size=20,color='mint'),
         B(93,310,1080,33,'python3 run_demo.py --output ./demo-live-01',font='Consolas',size=20,color='mint'),
         B(70,406,1110,65,'Open report/index.html and report/run-summary.json.',size=27,bold=True),
         B(72,504,1110,88,'Use a pregenerated synthetic report as backup. Keep its evidence directory and identify it as a prior run.',size=20,color='muted')],
    ]
    for i,(label,change,meaning) in enumerate((
        ('legacy_export','DEMO_1 → absent','Missing export'),
        ('added_export','Absent → DEMO_1','Added export'),
        ('version_contract','DEMO_2 → DEMO_3','Version change'),
        ('data_contract','4 B → 8 B','Data ABI break'),
        ('stable_code','Same export, larger function','Code size only'),
    )):
        y = 287+i*56
        slides[3].extend([B(70,y,1140,52,fill='panel' if i%2==0 else 'bg'),
                          B(88,y+13,310,32,label,size=16,font='Consolas'),
                          B(417,y+12,490,32,change,size=17),
                          B(933,y+12,257,32,meaning,size=16,color='coral' if i in (0,3) else 'muted')])
    return [items+footer() for items in slides]


def rels(entries):
    return f'<Relationships xmlns="{PKG}">'+''.join(
        f'<Relationship Id="{key}" Type="{kind}" Target="{target}"/>' for key,kind,target in entries
    )+'</Relationships>'


def relationships(entries):
    return rels((f'rId{i}',f'{REL}/{typ}',target) for i,(typ,target) in enumerate(entries,1))


def group_tree():
    return ('<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>')


def solid(col):
    return f'<a:solidFill><a:srgbClr val="{PALETTE[col]}"/></a:solidFill>'


def shape(i, box):
    fill = solid(box.fill) if box.fill else '<a:noFill/>'
    body = ''
    if box.value:
        paragraphs = ''.join(
            f'<a:p><a:pPr><a:lnSpc><a:spcPct val="112000"/></a:lnSpc></a:pPr>'
            f'<a:r><a:rPr lang="en-US" sz="{box.size*100}" b="{int(box.bold)}">{solid(box.color)}'
            f'<a:latin typeface="{box.font}"/></a:rPr><a:t xml:space="preserve">{escape(line)}</a:t></a:r></a:p>'
            for line in box.value.splitlines()
        )
        body = '<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0"/><a:lstStyle/>'+paragraphs+'</p:txBody>'
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Shape {i}"/><p:cNvSpPr txBox="{int(bool(body))}"/>'
        f'<p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{box.x*EMU}" y="{box.y*EMU}"/>'
        f'<a:ext cx="{box.width*EMU}" cy="{box.height*EMU}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>{fill}<a:ln><a:noFill/></a:ln></p:spPr>{body}</p:sp>'
    )


def slide_xml(boxes):
    drawing = '<p:bg><p:bgPr>'+solid('bg')+'<a:effectLst/></p:bgPr></p:bg>'
    shapes = ''.join(shape(i,box) for i,box in enumerate(boxes,2))
    return (f'<p:sld {NS}><p:cSld>{drawing}<p:spTree>{group_tree()}{shapes}</p:spTree></p:cSld>'
            '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')


def theme_xml():
    names = {
        'dk1':'0B1521','lt1':'F5F9FC','dk2':'142536','lt2':'B5C6D3',
        'accent1':'7DDFC2','accent2':'FFAA9B','accent3':'F5D589',
        'accent4':'83B8DC','accent5':'A2A3E0','accent6':'CC9EB8','hlink':'78C4FF','folHlink':'B6ABF3',
    }
    scheme = ''.join(f'<a:{key}><a:srgbClr val="{value}"/></a:{key}>' for key,value in names.items())
    font = '<a:latin typeface="Aptos"/><a:ea typeface=""/><a:cs typeface=""/>'
    fill = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    line = f'<a:ln w="9525">{fill}<a:prstDash val="solid"/></a:ln>'
    return (
        f'<a:theme xmlns:a="{A}" name="Tizen Demo"><a:themeElements><a:clrScheme name="Tizen">{scheme}</a:clrScheme>'
        f'<a:fontScheme name="Aptos"><a:majorFont>{font}</a:majorFont><a:minorFont>{font}</a:minorFont></a:fontScheme>'
        f'<a:fmtScheme name="Tizen"><a:fillStyleLst>{fill*3}</a:fillStyleLst><a:lnStyleLst>{line*3}</a:lnStyleLst>'
        '<a:effectStyleLst>'+('<a:effectStyle><a:effectLst/></a:effectStyle>'*3)+
        f'</a:effectStyleLst><a:bgFillStyleLst>{fill*3}</a:bgFillStyleLst></a:fmtScheme>'
        '</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>'
    )


def presentation_parts():
    slides = slide_content()
    overrides = ''.join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1,len(slides)+1)
    )
    ids = ''.join(f'<p:sldId id="{255+i}" r:id="rId{i+1}"/>' for i in range(1,len(slides)+1))
    background = (
        '<p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
        'accent6="accent6" bg1="dk1" bg2="dk2" folHlink="folHlink" hlink="hlink" tx1="lt1" tx2="lt2"/>'
    )
    tree = f'<p:cSld><p:spTree>{group_tree()}</p:spTree></p:cSld>'
    container = 'application/vnd.openxmlformats-officedocument.presentationml.'
    parts = {
        '[Content_Types].xml': f'<Types xmlns="{TYPES}">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/ppt/presentation.xml" ContentType="{container}presentation.main+xml"/>'
            f'<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="{container}slideMaster+xml"/>'
            f'<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="{container}slideLayout+xml"/>'
            '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
            f'{overrides}</Types>',
        '_rels/.rels':relationships([('officeDocument','ppt/presentation.xml')]),
        'ppt/presentation.xml':f'<p:presentation {NS}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
            f'</p:sldMasterIdLst><p:sldIdLst>{ids}</p:sldIdLst><p:sldSz cx="{WIDTH*EMU}" cy="{HEIGHT*EMU}"/>'
            '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>',
        'ppt/_rels/presentation.xml.rels':relationships([('slideMaster','slideMasters/slideMaster1.xml')]+
            [('slide', f'slides/slide{i}.xml') for i in range(1,len(slides)+1)]),
        'ppt/slideMasters/slideMaster1.xml':f'<p:sldMaster {NS}>{tree}{background}'
            '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>',
        'ppt/slideMasters/_rels/slideMaster1.xml.rels':relationships([
            ('slideLayout','../slideLayouts/slideLayout1.xml'),('theme','../theme/theme1.xml')]),
        'ppt/slideLayouts/slideLayout1.xml':f'<p:sldLayout {NS} type="blank" preserve="1">{tree}'
            '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>',
        'ppt/slideLayouts/_rels/slideLayout1.xml.rels':relationships([('slideMaster','../slideMasters/slideMaster1.xml')]),
        'ppt/theme/theme1.xml':theme_xml(),
    }
    for i,boxes in enumerate(slides,1):
        parts[f'ppt/slides/slide{i}.xml'] = slide_xml(boxes)
        parts[f'ppt/slides/_rels/slide{i}.xml.rels'] = relationships([('slideLayout','../slideLayouts/slideLayout1.xml')])
    return parts


def verify(path):
    with ZipFile(path) as file:
        if file.testzip():
            raise ValueError('Zip CRC check failed')
        names = set(file.namelist())
        for member in names:
            root = ET.fromstring(file.read(member))
            if member.endswith('.rels'):
                for ref in root:
                    resolved = posixpath.normpath(str(PurePosixPath(member).parent.parent/ref.attrib['Target']))
                    if resolved not in names or ref.attrib.get('TargetMode')=='External':
                        raise ValueError('Missing or external relationship '+resolved)
        slides = [name for name in names if name.startswith('ppt/slides/slide') and name.endswith('.xml')]
        if len(slides)!=8:
            raise ValueError('Unexpected slide count')
        return len(slides)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with ZipFile(args.output, mode='x') as file:
        for name,xml in presentation_parts().items():
            member = ZipInfo(name, date_time=(2024,1,1,0,0,0))
            file.writestr(member,(DECL+xml).encode(),ZIP_DEFLATED)
    print(f'Validated {verify(args.output)} slides with internal-only package relationships')


if __name__ == '__main__':
    main()
