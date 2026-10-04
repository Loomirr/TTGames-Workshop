"""Small offline editor for longer character and rigid-object instance names."""
import json,tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from cu3_name_editor import Cutscene,FormatError,inventory,rewrite_names,plan_character_replacement
from io_scene_lego_cu3.name_editor import character_key


class NameEditor:
    def __init__(self,window):
        self.window=window;self.cut=None;self.items={};self.edits={}
        window.title('CU3 Instance Name Editor — research');window.geometry('1100x660')
        toolbar=ttk.Frame(window,padding=12);toolbar.pack(fill='x')
        ttk.Button(toolbar,text='Open CU3…',command=self.open).pack(side='left')
        ttk.Button(toolbar,text='Save edited copy…',command=self.save).pack(side='right')
        self.path=tk.StringVar(value='Open an extracted, uncompressed PC CU3 file.');ttk.Label(toolbar,textvariable=self.path).pack(side='left',padx=16)
        table=ttk.Frame(window,padding=(12,0));table.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table,columns=('kind','index','old','new'),show='headings',selectmode='browse')
        for col,title,width in [('kind','Type',80),('index','Index',65),('old','Current name',425),('new','Replacement name',425)]:
            self.tree.heading(col,text=title);self.tree.column(col,width=width,anchor='w')
        scroll=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y');self.tree.bind('<<TreeviewSelect>>',self.select)
        edit=ttk.Frame(window,padding=12);edit.pack(fill='x')
        ttk.Label(edit,text='New name:').pack(side='left');self.name=tk.StringVar();ttk.Entry(edit,textvariable=self.name).pack(side='left',fill='x',expand=True,padx=10)
        ttk.Button(edit,text='Set replacement',command=self.set).pack(side='left');ttk.Button(edit,text='Restore selected',command=self.restore).pack(side='left',padx=8)
        ttk.Button(edit,text='Replace all character instances',command=self.replace_character).pack(side='left')
        self.status=tk.StringVar(value='Copies only. Animation bytes and scene structure are checked before saving. Game compatibility is not yet certified.')
        ttk.Label(window,textvariable=self.status,padding=12,wraplength=1060).pack(fill='x')
    def open(self):
        path=filedialog.askopenfilename(filetypes=[('CU3 files','*.CU3 *.cu3'),('All files','*.*')])
        if not path:return
        try:cut=Cutscene(path);data=inventory(cut)
        except (ValueError,OSError) as exc:messagebox.showerror('Unable to read CU3',str(exc));return
        self.cut=cut;self.items={};self.edits={};self.tree.delete(*self.tree.get_children())
        for kind,key in [('actor','actors'),('object','objects')]:
            for entry in data[key]:
                row=f'{kind}:{entry["index"]}';self.items[row]=(kind,entry['index'],entry['name'])
                self.tree.insert('',tk.END,iid=row,values=(kind,entry['index'],entry['name'],''))
        self.path.set(Path(path).name);self.name.set('')
        self.status.set(f'CU3 v{cut.version}; {cut.frames} frames at {cut.fps:g} FPS. Select one reference and enter a longer name. '+('Object table unavailable: '+data['object_layout_error'] if data['object_layout_error'] else ''))
    def select(self,event=None):
        selected=self.tree.selection()
        if selected:
            row=selected[0];self.name.set(self.edits.get(row,self.items[row][2]))
            kind,index,_=self.items[row]
            if kind=='actor':
                actor=self.cut.actors[index]
                self.status.set(f"Numeric resource reference: {actor.get('metadata',{}).get('actor_id')}; animation labels: "+', '.join(r['name'] for r in actor['records'])+'. Labels are preserved independently; instance numbers do not imply playback order.')
    def replace_character(self):
        selected=self.tree.selection()
        if not selected or not self.cut:return
        kind,index,old=self.items[selected[0]]
        if kind!='actor' or self.cut.actors[index]['parent'] is not None:
            messagebox.showerror('Select a character','Select a root actor instance.');return
        try:
            names,plan=plan_character_replacement(self.cut,character_key(old)[1],character_key(self.name.get())[1])
            for ai,value in names.items():
                row=f'actor:{ai}';_,_,previous=self.items[row]
                self.edits[row]=value;self.tree.item(row,values=('actor',ai,previous,value))
            self.status.set(f'{len(names)} character instances prepared. Review the replacement column before saving. Animation-record labels and numeric references remain preserved.')
        except FormatError as exc:messagebox.showerror('Invalid character replacement',str(exc))
    def set(self):
        selected=self.tree.selection()
        if not selected:return
        row=selected[0];value=self.name.get();kind,index,old=self.items[row]
        try:
            from io_scene_lego_cu3.name_editor import _name
            _name(value)
        except FormatError as exc:messagebox.showerror('Invalid name',str(exc));return
        self.edits[row]=value;self.tree.item(row,values=(kind,index,old,value));self.status.set(f'{len(self.edits)} pending replacements. Source file remains unchanged.')
    def restore(self):
        selected=self.tree.selection()
        if selected:
            row=selected[0];self.edits.pop(row,None);kind,index,old=self.items[row];self.tree.item(row,values=(kind,index,old,''));self.name.set(old)
    def save(self):
        if not self.cut or not self.edits:messagebox.showinfo('Nothing to save','Open a file and set at least one replacement.');return
        actors={};objects={}
        for row,name in self.edits.items():
            kind,index,old=self.items[row];(actors if kind=='actor' else objects)[index]=name
        try:data,report=rewrite_names(self.cut,actors,objects)
        except (ValueError,OSError) as exc:messagebox.showerror('Validation failed',str(exc));return
        target=filedialog.asksaveasfilename(initialfile=self.cut.path.stem+'_Renamed.CU3',defaultextension='.CU3',filetypes=[('CU3 file','*.CU3')])
        if not target:return
        path=Path(target)
        if path.resolve()==self.cut.path.resolve():messagebox.showerror('Source protected','Choose a different output filename.');return
        try:
            path.write_bytes(data);path.with_suffix(path.suffix+'.rename.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        except OSError as exc:messagebox.showerror('Unable to save',str(exc));return
        self.status.set(f'Saved {path.name}. Structural validation passed; original animation blob preserved. Test game loading separately. Character/object assets and script references may also require changes.')


if __name__=='__main__':
    window=tk.Tk();NameEditor(window);window.mainloop()
