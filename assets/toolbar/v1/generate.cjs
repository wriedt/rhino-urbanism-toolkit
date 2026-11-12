// Rebuild with: node generate.cjs <path-to-sharp-module>
// Original RUT vector artwork. No runtime dependency for the plugin.
const fs = require('node:fs');
const path = require('node:path');
const sharp = require(process.argv[2] || 'sharp');
const out = __dirname;
const themes = {
  light: {ink:'#263f4b',muted:'#526d76',accent:'#246e7b',fill:'#e2f1ed',bg:'#f6f8f8'},
  dark: {ink:'#e9f5f6',muted:'#b9d0d5',accent:'#b1e4df',fill:'#294944',bg:'#223138'}
};
const line=(d,c='ink',w=1.6)=>`<path d="${d}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;
const face=(d,c='accent',f='fill')=>`<path d="${d}" fill="${f}" stroke="${c}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>`;
const circle=(x,y,r,c='accent')=>`<circle cx="${x}" cy="${y}" r="${r}" fill="none" stroke="${c}" stroke-width="1.6"/>`;
const stack=()=>line('M3 13 10 16.5 17 13 M3 17 10 20.5 17 17','muted')+face('M3 9 10 5.5 17 9 10 12.5Z');
const cube=()=>face('M3 7 9 3.5 15 7 15 14 9 17.5 3 14Z','ink')+line('M3 7 9 10.5 15 7 M9 10.5V17.5','ink');
const lock=(open=false)=>face('M14 14H22V21H14Z','accent')+line(open?'M16 14V11.5C16 8 21 8 21 11':'M16 14V11.5C16 8 20 8 20 11.5V14','accent');
const eye=()=>face('M12 8Q17 2 22 8Q17 14 12 8Z')+circle(17,8,1.4);
const back=()=>line('M18 4H21V7 M21 4C15 2 13 5 13 8','accent');
const plus=()=>line('M18 14V22 M14 18H22','accent',2);
const icons=[
 ['RUTIsolateLayer','Isolate layers',stack()+line('M2 4V2H6 M18 2H22V6 M22 17V22H18 M6 22H2V19','accent')],
 ['RUTUnisolateLayer','Restore visibility',stack()+back()],
 ['RUTIsolateLockLayer','Isolate by locking',stack()+lock()],
 ['RUTUnisolateLockLayer','Restore layer locks',lock(true)+line('M3 9H10V16 M10 9C2 8 1 17 7 21','accent')],
 ['RUTShowAllLayers','Show all layers',stack()+eye()],
 ['RUTUnlockAllLayers','Unlock all layers',stack()+lock(true)],
 ['RUTShowAndUnlockAllLayers','Show and unlock',line('M2 8 7 5 12 8 7 11Z M2 13 7 16 11 14 M2 18 7 21 11 19','ink')+eye()+lock(true)],
 ['RUTToggleLayerExpansion','Expand / collapse',line('M4 3V18H9 M4 9H9','muted')+face('M10 6H17V11H10Z')+face('M10 15H17V20H10Z')+line('M20 4 22 2 24 4 M20 20 22 22 24 20','accent')],
 ['RUTCreateBlockVersion','Create block version',cube()+plus()],
 ['RUTConsolidateBlockVersions','Consolidate versions',cube()+line('M18 5H22 M18 10H22 M18 15H22 M17 20H22 M18 18 16 20 18 22','accent')],
 ['RUTRenameBlockFamily','Rename block family',cube()+face('M13 19 19 13 22 16 16 22 12 23Z','accent')+line('M18 14 21 17','accent')],
 ['RUTAssignBlockLayer','Assign home layer',cube()+face('M13 18 18 15 23 18 18 21Z')+line('M20 3V11 M17 8 20 11 23 8','accent')],
 ['RUTApplyBlockLayers','Apply home layers',cube()+face('M13 18 18 15 23 18 18 21Z')+line('M17 6 19 8 23 3','accent',2)],
 ['RUTShowBlockLayers','Review home layers',cube()+circle(18,17,3.5)+line('M20.5 19.5 23 22','accent')],
 ['RUTQuickFloorArea','Quick floor area',face('M2 10 12 5 20 9 10 14Z')+line('M5 10 12 7 M9 12 16 8','accent',1.2)+face('M14 13H22V22H14Z','ink')+line('M16 13V11H20V13 M16 17H20 M16 19.5H19','ink',1.2)],
 ['RUTFloorArea','Floor area inspector',face('M3 8 10 4 17 8 17 18 10 22 3 18Z','ink')+line('M3 8 10 12 17 8 M10 12V22','muted')+face('M2 13 10 9 18 13 10 17Z')+line('M22 5V21 M20 5H23 M20 13H23 M20 21H23','accent')],
 ['RUTPushPullCurve','Push / pull curve',line('M3 4V21H21 M3 4H11V10','ink')+line('M15 4V16 M11 10H22 M19 7 22 10 19 13','accent',2)+line('M11 16H15','muted',1.2)],
 ['RUTShapeBuilder','Shape builder',face('M3 4H13V9H21V21H9V16H3Z')+line('M5 7 9 11 M9 7 13 11 M12 14 17 19 M16 13 19 16','accent',1.2)]
];
function colour(markup,t) {
  return markup.replace(/(stroke|fill)="(ink|muted|accent|fill)"/g,(_,attr,key)=>`${attr}="${t[key]}"`);
}
function svg(command,markup,t) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 26 26"><title>${command}</title><g transform="translate(1 1)">${colour(markup,t)}</g></svg>`;
}
async function main(){
 const manifest=[];
 for(const [command,label,markup] of icons){
  const entry={command,label,conditional:['RUTPushPullCurve','RUTShapeBuilder'].includes(command),icons:{}};
  for(const [mode,t] of Object.entries(themes)){
   const dir=path.join(out,mode); fs.mkdirSync(dir,{recursive:true});
   const image=svg(command,markup,t); fs.writeFileSync(path.join(dir,command+'.svg'),image+'\n');
   entry.icons[mode]=mode+'/'+command+'.svg';
   for(const size of [24,32,48]) await sharp(Buffer.from(image)).resize(size,size).png().toFile(path.join(dir,`${command}-${size}.png`));
  }
  manifest.push(entry);
 }
 fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
 let sheet='<svg xmlns="http://www.w3.org/2000/svg" width="1020" height="900" viewBox="0 0 1020 900">';
 for(const [j,[mode,t]] of Object.entries(themes).entries()){
  const x=j*510;
  sheet+=`<rect x="${x}" width="510" height="900" fill="${t.bg}"/><g fill="${t.ink}" font-family="Segoe UI, sans-serif"><text x="${x+22}" y="34" font-size="22">RUT toolbar icons / ${mode}</text><text x="${x+22}" y="59" font-size="13">Draft v1 · actual 24 / 32 / 48 px · * conditional</text></g>`;
  icons.forEach(([command,label,markup],i)=>{
   const cx=x+22+(i%3)*163, cy=90+Math.floor(i/3)*131;
   for(const [k,size] of [24,32,48].entries()){
    const ix=cx+[0,34,76][k];
    sheet+=`<svg x="${ix}" y="${cy+(48-size)/2}" width="${size}" height="${size}" viewBox="0 0 26 26"><g transform="translate(1 1)">${colour(markup,t)}</g></svg>`;
   }
   const words=label.split(' '); let rows=[''];
   for(const word of words){if((rows.at(-1)+' '+word).trim().length>20) rows.push(word);else rows[rows.length-1]=(rows.at(-1)+' '+word).trim();}
   if(i>=16) rows[rows.length-1]+=' *';
   rows.forEach((row,k)=>sheet+=`<text x="${cx}" y="${cy+74+k*18}" fill="${t.ink}" font-family="Segoe UI, sans-serif" font-size="13">${row}</text>`);
  });
 }
 sheet+='</svg>';
 fs.writeFileSync(path.join(out,'preview.svg'),sheet+'\n');
 await sharp(Buffer.from(sheet)).png().toFile(path.join(out,'preview.png'));
 console.log('Created 36 SVG icons, 108 transparent PNGs, manifest and preview.');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
