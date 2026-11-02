"""Preserve native source captures and arrange explicit before/after report panels."""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image,ImageDraw,ImageFont
from sensor_msgs.msg import Image as ROSImage


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--motion-run',type=Path,required=True)
    parser.add_argument('--terrain-run',type=Path,required=True)
    args=parser.parse_args()
    out=Path(__file__).resolve().parent
    font=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',30)
    sources=[]
    for view,prefix in (('gazebo','scene'),('rviz','sensors')):
        for stage in ('before','after'):
            receipt=json.loads((args.motion_run/'figures'/(view+'-'+stage+'.json')).read_text())
            source=Path(receipt['file']); target=out/(prefix+'-'+stage+'.png')
            shutil.copy2(source,target)
            sources.append(dict(file=target.name,source=str(source),operation='exact copy'))
    rows=json.loads((args.motion_run/'receipts.json').read_text())['rows']
    for stage,row in zip(('before','after'),(rows['infrared'][0],rows['infrared'][-1])):
        source=args.motion_run/row['wire'];message=ROSImage().deserialize(source.read_bytes())
        pixels=np.frombuffer(message.data,dtype='<f4').reshape(message.height,message.width)
        Image.fromarray(np.rint(pixels*255).astype('uint8')).save(out/('infrared-'+stage+'.png'))
        sources.append(dict(file='infrared-'+stage+'.png',source=str(source),
            timestamp_ns=message.header.stamp.to_nsec(),operation='raw float intensity 0..1 to fixed grayscale 0..255'))
    for name,relative in [('elevation-map.png','elevation-map.png'),('elevation-rviz.png','figures/real-elevation.png')]:
        source=args.terrain_run/relative;shutil.copy2(source,out/name)
        sources.append(dict(file=name,source=str(source),operation='exact copy'))
    panel=Image.new('RGB',(1500,2020),'white');draw=ImageDraw.Draw(panel)
    for i,stage in enumerate(('before','after')):
        draw.text((20,i*1010+8),'t = '+('0.100 s' if i==0 else '1.000 s')+' | Radar and IR',font=font,fill='black')
        panel.paste(Image.open(out/('sensors-'+stage+'.png')).convert('RGB'),(0,i*1010+60))
    panel.save(out/'motion-observations.png')
    sources.append(dict(file='motion-observations.png',sources=['sensors-before.png','sensors-after.png'],
        operation='two unaltered full native screenshots with external timestamp captions'))
    panel=Image.new('RGB',(1340,570),'white');draw=ImageDraw.Draw(panel)
    for i,stage in enumerate(('before','after')):
        draw.text((i*670+12,8),'t = '+('0.100 s' if i==0 else '1.000 s'),font=font,fill='black')
        im=Image.open(out/('infrared-'+stage+'.png')).resize((640,480),Image.Resampling.NEAREST)
        panel.paste(im,(i*670+10,65))
    panel.save(out/'infrared-comparison.png')
    sources.append(dict(file='infrared-comparison.png',sources=['infrared-before.png','infrared-after.png'],
        operation='fixed grayscale raw IR side-by-side; nearest pixel enlargement'))
    (out/'sources.json').write_text(json.dumps(dict(motion_run=str(args.motion_run.resolve()),
        terrain_run=str(args.terrain_run.resolve()),figures=sources),indent=2)+'\n')
    print(out)


if __name__=='__main__':main()
