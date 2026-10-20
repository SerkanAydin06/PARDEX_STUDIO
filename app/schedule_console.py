"""PARDEX 2H user-facing planner; no model calls or automatic daemon."""
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox
import shift_scheduler as scheduler
import worker_supervisor as worker

class ShiftPlanner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('PARDEX — AI Vardiya Planlayıcı')
        self.geometry('840x560')
        self.minsize(690,470)
        self.ids=()
        main=ttk.Frame(self,padding=16);main.pack(fill='both',expand=True)
        ttk.Label(main,text='PARDEX — Zamanlanmış AI Vardiyaları',
                  font=('Segoe UI',17,'bold')).pack(anchor='w',pady=(0,8))
        ttk.Label(main,text='Yalnızca önceden tek tek onayladığın en fazla 2 görev planlanır.').pack(anchor='w')
        bar=ttk.Frame(main);bar.pack(anchor='w',pady=9)
        ttk.Label(bar,text='Kaç dakika sonra?').grid(row=0,column=0)
        self.delay=tk.StringVar(value='60')
        ttk.Entry(bar,textvariable=self.delay,width=8).grid(row=0,column=1,padx=10)
        ttk.Label(bar,text='Geçerlilik (dk)').grid(row=0,column=2)
        self.window=tk.StringVar(value='20')
        ttk.Entry(bar,textvariable=self.window,width=8).grid(row=0,column=3,padx=10)
        self.native=tk.BooleanVar(value=False)
        ttk.Checkbutton(main,variable=self.native,
            text='Ayrıca onaylıyorum: native CLI izole DEĞİLDİR ve üyelik kotası kullanabilir.').pack(anchor='w',pady=4)
        actions=ttk.Frame(main);actions.pack(fill='x',pady=8)
        ttk.Button(actions,text='Ücretsiz görev önizleme',command=self.preview).pack(side='left',padx=3)
        ttk.Button(actions,text='Plan oluştur',command=self.create).pack(side='left',padx=3)
        ttk.Button(actions,text='Planları göster',command=self.list_plans).pack(side='left',padx=3)
        ttk.Button(actions,text='Zamanı gelenler',command=self.due).pack(side='left',padx=3)
        ttk.Label(main,foreground='#a66011',
            text='Bu pencere saat gelince otomatik AI başlatmaz. Ayrı Windows zamanlayıcısı gerekir.\n'
                 'Sıkı güvenlik modunda izole olmayan AI işleri her durumda durur.').pack(anchor='w',pady=4)
        panel=ttk.Frame(main);panel.pack(fill='both',expand=True,pady=8)
        self.log=tk.Text(panel,state='disabled',wrap='word',font=('Consolas',10))
        self.log.pack(side='left',fill='both',expand=True)
        scrollbar=ttk.Scrollbar(panel,command=self.log.yview);scrollbar.pack(side='right',fill='y')
        self.log.config(yscrollcommand=scrollbar.set)
        self.preview()

    def write(self,text):
        self.log.config(state='normal')
        self.log.insert('end',str(text)+'\n')
        self.log.see('end')
        self.log.config(state='disabled')

    def preview(self):
        self.ids=()
        try:
            data=worker.preview(max_tasks=2,max_minutes=30)
            if data.get('blocked_reason'):
                self.write('Engel: '+str(data['blocked_reason']));return
            self.ids=tuple(x['id'] for x in data['tasks'])
            self.write('Hazır görevler (ücretsiz önizleme):')
            for task in data['tasks']:
                self.write(task['id']+' | '+task['project']+' | '+task['provider'])
            if not self.ids:self.write('Şu anda planlanabilir onaylı görev yok.')
        except Exception as error:
            self.write('Önizleme hatası: '+type(error).__name__)

    def create(self):
        if not self.ids:
            messagebox.showinfo('Görev yok','Önce onaylı görevleri önizle.');return
        try:
            delay=int(self.delay.get());window=int(self.window.get())
            if not 1<=delay<=10080 or not 1<=window<=60:
                raise ValueError('invalid delay')
        except ValueError:
            messagebox.showerror('Süre','Başlangıç 1–10080, geçerlilik 1–60 dakika olmalı.');return
        risk=('Native AI çalışması abonelik kotası tüketebilir ve OS izolasyonu yoktur.'
              if self.native.get() else 'Varsayılan: otomatik native AI çalışması kapalı kalır.')
        if not messagebox.askyesno('Açık sahip onayı',
            'Şu görevleri tek kullanımlık planlamak istiyor musun?\n'
            +'\n'.join(self.ids)+'\n\n'+risk+'\nSonuç kabulü ayrıca gereklidir.'):
            return
        start=datetime.now().astimezone()+timedelta(minutes=delay)
        try:
            rec=scheduler.plan(self.ids,start,start+timedelta(minutes=window),
                 owner_confirms=True,allow_native_unisolated=self.native.get())
            self.write('Plan oluşturuldu: '+rec['id']+' | Henüz hiçbir AI çağrılmadı.')
            self.ids=()
        except Exception as error:
            self.write('Plan oluşturulamadı: '+type(error).__name__+': '+str(error)[:140])

    def list_plans(self):
        try:
            for item in scheduler.all_schedules(limit=15):
                self.write(item['id']+' | '+item['state']+' | '+item['run_at'])
        except Exception as error:
            self.write('Liste hatası: '+type(error).__name__)

    def due(self):
        try:
            report=scheduler.preview_due()
            self.write('Vadesi gelen: '+str(len(report['due']))+
                 ' | süresi geçmiş: '+str(len(report['expired_ids']))+
                 ' | AI çağrısı: 0')
        except Exception as error:
            self.write('Kontrol hatası: '+type(error).__name__)

if __name__=='__main__':
    ShiftPlanner().mainloop()
