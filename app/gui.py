"""Turkish desktop GUI for Ultra Pro Studio. Built-in Tkinter (no pip dependencies)."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
import core
import brain
import evolution
import company
import task_queue

BG='#0c1220'; PANEL='#172236'; PANEL2='#202e46'; FG='#ebf2ff'; SUB='#aebdd7'; BLUE='#628eea'; GREEN='#60d4ac'

class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Ultra Pro AI Studio v5 · AI Sirket Merkezi')
        self.geometry('1130x850'); self.minsize(920,690)
        self.configure(bg=BG)
        self.busy=False
        self.v_proj=tk.StringVar(value='Proje secilmedi')
        self.v_engine=tk.StringVar(value='godot')
        self.v_root=tk.StringVar(value=str(Path.home()/'Documents'/'UltraProProjects'))
        self.v_name=tk.StringVar(value='YeniOyun')
        self.v_provider=tk.StringVar(value='Otomatik')
        self.v_quality=tk.StringVar(value='Dengeli')
        self.v_kind=tk.StringVar(value='Yeni ozellik / Kod')
        self.v_day=tk.IntVar(value=8)
        self.v_mins=tk.IntVar(value=15)
        self.v_asset=tk.StringVar(value='2D')
        self.v_saved=tk.StringVar(value='')
        self.v_proposal=tk.StringVar(value='')
        self.v_role=tk.StringVar(value='implementer')
        self.v_auto_council=tk.BooleanVar(value=False)
        self.v_auto_text=tk.BooleanVar(value=False)
        self.v_candidate=tk.StringVar(value='')
        self.v_server=tk.StringVar(value='web')
        self.v_ollama_model=tk.StringVar(value='qwen3:4b')
        self.v_subname=tk.StringVar(value='Yeni ucretli arac')
        self.v_subcost=tk.StringVar(value='10')
        self.v_subhours=tk.StringVar(value='2')
        self.v_hourvalue=tk.StringVar(value='10')
        self.v_rec=tk.StringVar(value='')
        self.v_queue_id=tk.StringVar(value='')
        self.v_queue_priority=tk.IntVar(value=3)
        self._style()
        self._layout()
        self.refresh()
        self.after(300,self.load_state)

    def _style(self):
        style=ttk.Style(self)
        style.theme_use('clam')
        style.configure('.',font=('Segoe UI',11))
        style.configure('TFrame',background=BG)
        style.configure('Pane.TFrame',background=PANEL)
        style.configure('TLabel',background=BG,foreground=FG,font=('Segoe UI',11))
        style.configure('Dim.TLabel',foreground=SUB)
        style.configure('H1.TLabel',font=('Segoe UI Semibold',19),foreground=FG)
        style.configure('H2.TLabel',font=('Segoe UI Semibold',13),foreground=FG)
        style.configure('TNotebook',background=BG,borderwidth=0)
        style.configure('TNotebook.Tab',background=PANEL2,foreground=FG,padding=(12,10),font=('Segoe UI Semibold',10))
        style.map('TNotebook.Tab',background=[('selected',BLUE)],foreground=[('selected','white')])
        style.configure('TButton',padding=8,background=BLUE,foreground='white',font=('Segoe UI Semibold',10),borderwidth=0)
        style.map('TButton',background=[('active','#3e74df'),('disabled','#56647a')])
        style.configure('TEntry',fieldbackground=PANEL2,foreground=FG,insertcolor=FG,padding=6)
        style.configure('TCombobox',fieldbackground=PANEL2,foreground='#142033',padding=6)
        style.configure('TSpinbox',fieldbackground=PANEL2,foreground=FG)
        style.configure('TCheckbutton',background=BG,foreground=FG,font=('Segoe UI',10))
        style.map('TCheckbutton',background=[('active',BG)],foreground=[('active',FG)])

    def lbl(self,parent,text='',style=None,**kw):
        return ttk.Label(parent,text=text,style=style or 'TLabel',wraplength=kw.pop('wraplength',890),**kw)
    def hint(self,parent,text):
        l=self.lbl(parent,text,'Dim.TLabel'); l.pack(anchor='w',pady=(1,9));return l
    def header(self,parent,title,subtitle):
        self.lbl(parent,title,'H1.TLabel').pack(anchor='w',pady=(6,3))
        self.hint(parent,subtitle)
    def btn(self,parent,text,fn):
        b=ttk.Button(parent,text=text,command=fn);b.pack(side='left',padx=(0,9),pady=5);return b
    def formrow(self,parent,label,var,width=70):
        self.lbl(parent,label,'H2.TLabel').pack(anchor='w',pady=(11,4))
        e=ttk.Entry(parent,textvariable=var,width=width);e.pack(fill='x',pady=2)
        return e
    def text(self,parent,height=7):
        widget=tk.Text(parent,height=height,bg=PANEL2,fg=FG,insertbackground=FG,
            selectbackground='#4964ac',font=('Consolas',10),bd=0,padx=12,pady=9,wrap='word')
        widget.pack(fill='both',expand=False,pady=3);return widget
    def log(self,message):
        self.after(0,lambda:self._log(message))
    def _log(self,message):
        self.console.configure(state='normal')
        self.console.insert('end',message.rstrip()+'\n'); self.console.see('end')
        while int(self.console.index('end-1c').split('.')[0])>320:
            self.console.delete('1.0','3.0')
        self.console.configure(state='disabled')
    def _inner(self, tab):
        canvas=tk.Canvas(tab,bg=BG,highlightthickness=0,bd=0)
        scrollbar=ttk.Scrollbar(tab,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y')
        canvas.pack(side='left',fill='both',expand=True)
        inside=ttk.Frame(canvas,padding=16)
        item=canvas.create_window((0,0),window=inside,anchor='nw')
        inside.bind('<Configure>',lambda ev:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda ev:canvas.itemconfig(item,width=ev.width))
        def scroll(ev):
            canvas.yview_scroll(-1 if ev.delta>0 else 1,'units')
        canvas.bind('<Enter>',lambda ev:canvas.bind_all('<MouseWheel>',scroll))
        canvas.bind('<Leave>',lambda ev:canvas.unbind_all('<MouseWheel>'))
        return inside

    def _layout(self):
        head=ttk.Frame(self);head.pack(fill='x',padx=24,pady=(16,6))
        self.lbl(head,'✦ ULTRA PRO STUDIO','H1.TLabel').pack(side='left')
        self.lbl(head,'Çoklu proje · AI yönetim kurulu · Onaylı gelişim · GitHub','Dim.TLabel').pack(side='right')
        self.lbl(self,textvariable=self.v_proj,style='Dim.TLabel').pack(anchor='w',padx=25)
        self.tabs=ttk.Notebook(self)
        self.p_home=ttk.Frame(self.tabs,padding=16);self.p_proj=ttk.Frame(self.tabs,padding=16)
        self.p_agent=ttk.Frame(self.tabs,padding=16);self.p_queue=ttk.Frame(self.tabs,padding=16);self.p_test=ttk.Frame(self.tabs,padding=16)
        self.p_assets=ttk.Frame(self.tabs,padding=16);self.p_git=ttk.Frame(self.tabs,padding=16)
        self.p_sys=ttk.Frame(self.tabs,padding=16)
        self.p_council=ttk.Frame(self.tabs,padding=16)
        self.p_radar=ttk.Frame(self.tabs,padding=16)
        self.p_company=ttk.Frame(self.tabs,padding=16)
        for tab,title in [(self.p_home,'Başlangıç'),(self.p_proj,'Projeler'),(self.p_agent,'AI Ekibi'),(self.p_queue,'Gorev Merkezi'),
                (self.p_test,'Test & Öğrenme'),(self.p_company,'AI Şirketi'),(self.p_council,'Çekirdek Konseyi'),(self.p_radar,'İnternet Radarı'),(self.p_assets,'Görsel Atölyesi'),(self.p_git,'GitHub'),(self.p_sys,'Sistem')]:
            self.tabs.add(tab,text=title)
        foot=ttk.Frame(self);foot.pack(side='bottom',fill='x',padx=24,pady=(0,12))
        self.lbl(foot,'İşlem kayıtları (hesap tokenları saklanmaz)','Dim.TLabel').pack(anchor='w')
        self.console=tk.Text(foot,height=6,bg=PANEL,fg=SUB,font=('Consolas',9),state='disabled',bd=0,padx=8)
        self.console.pack(fill='x')
        self.tabs.pack(fill='both',expand=True,padx=17,pady=(12,6))
        self._home();self._projects();self._agents();self._queue_tab();self._testing();self._company();self._council();self._radar();self._assets();self._github();self._system()

    def _home(self):
        p=self._inner(self.p_home)
        self.header(p,'Hoş geldin!','1. Bir proje oluştur veya bağla  →  2. Hedef yaz  →  3. AI görevi çalıştır  →  4. Testi incele  →  5. Oyunu kendin dene.')
        self.lbl(p,'Akıllı iş dağılımı','H2.TLabel').pack(anchor='w',pady=(12,5))
        for x in ('Kod yazma / hata düzeltme → Codex (ChatGPT Pro hesabı)',
                  'Mimari ve plan → Claude Code (güncel Sonnet)',
                  'Bağımsız analiz → Gemini CLI (Auto / Pro)',
                  '2D görseller → ChatGPT + Gemini arayüzü',
                  '3D modeller → Meshy.ai arayüzü'):
            self.hint(p,'• '+x)
        self.lbl(p,'Kota koruma: aynı anda tek AI görevi; günlük yerel çağrı sayacı ve süre sınırı. Bu sayaç gerçek sağlayıcı token kotası değildir.','Dim.TLabel').pack(anchor='w',pady=8)
        line=ttk.Frame(p);line.pack(anchor='w',pady=12)
        self.btn(line,'Yeni proje',lambda:self.tabs.select(self.p_proj))
        self.btn(line,'Görev yaz',lambda:self.tabs.select(self.p_agent))
        self.btn(line,'Programları kontrol et',lambda:self.tabs.select(self.p_sys))
        self.btn(line,'Sıradaki adım ne?',self.suggest_step)

    def _council(self):
        p=self._inner(self.p_council)
        self.header(p,'Yapay Zekâ Denetim Konseyi',
            'Bir projeye özgü hata çekirdeği bozmaz. Kanıtlar toplanır, farklı yapay zekâlar çözümü denetler, güvenli talimatlar sürümlenir.')
        self.council_stats=self.lbl(p,'Yükleniyor...','Dim.TLabel');self.council_stats.pack(anchor='w',pady=6)
        row=ttk.Frame(p);row.pack(anchor='w',pady=5)
        self.btn(row,'Hataları ve kuralları yenile',self.refresh_council)
        self.btn(row,'AI ile iyileştirme öner',self.propose_from_ai)
        self.lbl(p,'İncelenecek öneri','H2.TLabel').pack(anchor='w',pady=(8,3))
        self.proposal_list=ttk.Combobox(p,textvariable=self.v_proposal,state='readonly')
        self.proposal_list.pack(fill='x',pady=3)
        row=ttk.Frame(p);row.pack(anchor='w',pady=6)
        self.btn(row,'Claude + Gemini ile denetle',self.review_proposal)
        self.btn(row,'İki AI onaylı kuralı etkinleştir',self.activate_proposal)
        self.btn(row,'Önceki kurala dön',self.rollback_rule)
        self.lbl(p,'Kontrollü kendi kendine öğrenme','H2.TLabel').pack(anchor='w',pady=(12,4))
        ttk.Checkbutton(p,text='Görev hatasında, yeterli kanıt varsa AI denetimini kendisi başlatsın (kota tüketir)',
                        variable=self.v_auto_council,command=self.save_council_settings).pack(anchor='w',pady=3)
        self.hint(p,'Talimatlar iki AI onaylasa da sen etkinlestirene kadar sadece oneridir. Otomatik etkinlestirme devre disidir.')
        self.hint(p,'AI kodu, güvenlik ayarlarını ve GitHub hesaplarını izinsiz değiştirmez. Talimat değişiklikleri geçmişe alınabilir.')
        self.lbl(p,'Kendi çekirdek kodunu geliştirmek için güvenli deneme alanı','H2.TLabel').pack(anchor='w',pady=(14,4))
        self.core_goal=self.text(p,3)
        self.core_goal.insert('1.0','AI stüdyosunun görev yönetimini ve hata sınıflandırmasını iyileştir; mevcut testleri koru.')
        row=ttk.Frame(p);row.pack(anchor='w')
        self.btn(row,'Çekirdek için deneme kopyası oluştur',self.prepare_candidate)
        self.btn(row,'Codex ile kopyayı geliştir',self.code_candidate)
        self.btn(row,'Test + iki AI kod incelemesi',self.audit_candidate)
        row=ttk.Frame(p);row.pack(anchor='w',pady=3)
        self.btn(row,'Onaylanan kodu stüdyoya uygula',self.install_candidate)
        self.btn(row,'Son kod güncellemesini geri al',self.rollback_code)
        self.hint(p,'Kod önce AYRI kopyada ve testlerle doğrulanır. İki AI onayı sonrasında kurulumu ayrıca sen onaylarsın. Geri alma yedeği alınır, sonra uygulama yeniden başlatılır.')
        self.council_report=self.text(p,13)
        self.refresh_council()

    def _radar(self):
        p=self._inner(self.p_radar)
        self.header(p,'Resmî teknoloji ve sürüm radarı',
            'Godot, Flutter, Codex, Gemini CLI ve Claude Code gibi araçların resmî GitHub sürümlerini okur; internetteki kodu çalıştırmaz.')
        row=ttk.Frame(p);row.pack(anchor='w',pady=5)
        self.btn(row,'Resmî GitHub sürümlerini tara',self.scan_radar)
        self.btn(row,'Raporu yeniden göster',self.show_radar)
        self.btn(row,'Gemini/Claude ile fırsatları değerlendir',self.ai_radar)
        self.radar_output=self.text(p,21)
        self.hint(p,'Yeni sürüm daha iyi olmak zorunda değil. Önce doğrulama, uyumluluk, regresyon ve bağımsız inceleme gerekir.')
        self.show_radar()

    def refresh_council(self):
        evidence=brain.evidence_summary()
        st=brain.settings()
        self.v_auto_council.set(st['auto_council'])
        self.v_auto_text.set(False)
        current=brain.policy()
        self.council_stats.configure(text=f"Çekirdek politika v{current['version']} · {len(brain.list_projects())} proje · {evidence['failures']} hata kaydı · {evidence['affected_projects']} farklı projede hata")
        items=brain.proposals()
        self.proposal_list['values']=[x['id']+' | '+x['role']+' | '+x['state'] for x in reversed(items)]
        if items and not self.v_proposal.get():self.v_proposal.set(self.proposal_list['values'][0])
        msg='GÜNCEL ÇEKİRDEK KURALLARI\n'
        for role,rules in current['rules'].items():
            msg+='\n'+role.upper()+'\n'+'\n'.join('• '+r for r in rules)+'\n'
        msg+='\nSON HATALAR\n'
        for ob in evidence['recent']:
            msg+='• '+ob['project'].split(os.sep)[-1]+' / '+ob['provider']+': '+ob['test'][:160]+'\n'
        msg+='\nÖNERİLER\n'
        for x in items[-8:]:msg+='• '+x['id']+' ['+x['state']+'] '+x['rule'][:130]+'\n'
        self.council_report.delete('1.0','end');self.council_report.insert('1.0',msg)

    def selected_proposal(self):
        val=self.v_proposal.get().split(' | ')[0]
        if not val:raise ValueError('Önce bir öneri seç')
        return val

    def save_council_settings(self):
        brain.change_settings({'auto_council':self.v_auto_council.get(), 'auto_text_policy':False})
        self.log('Çekirdek AI konsey ayarları kaydedildi.')

    def propose_from_ai(self):
        if not messagebox.askyesno('AI önerisi','Doğrulanmış hatalardan yeni bir kural önerisi üretilecek. Bu işlem bir AI çağrısı tüketir. Devam?'):return
        def worker():
            item=brain.generate_rule_from_incidents()
            self.log('Yeni öneri: '+item['id']+' '+item['rule'])
            self.after(0,self.refresh_council)
        self.run_background(worker)

    def review_proposal(self):
        try:ident=self.selected_proposal()
        except Exception as e:messagebox.showwarning('Seçim',str(e));return
        if not messagebox.askyesno('Bağımsız AI incelemesi','Claude ve Gemini ile bağımsız talimat denetimi yapılacak (2 AI çağrısı). Devam edilsin mi?'):return
        def worker():
            for provider in ('Claude','Gemini'):
                self.log(provider+' çekirdek talimatını denetliyor...')
                brain.model_review(ident,provider)
            self.log('Denetim bitti: '+str(brain.eligibility(ident)))
            self.after(0,self.refresh_council)
        self.run_background(worker)

    def activate_proposal(self):
        try:
            ident=self.selected_proposal();ok,why=brain.eligibility(ident)
            if not ok:raise ValueError(why)
            if not messagebox.askyesno('Çekirdek kuralını güncelle','İki farklı yapay zekâ tarafından onaylandı. Yeni sürüm kaydedilecek ve geri alma yedeği alınacak. Devam mı?'):return
            version=brain.activate_rule(ident,owner_approved=True)
            self.log('Çekirdek rol kuralları v'+str(version)+' oldu.');self.refresh_council()
        except Exception as e:messagebox.showerror('Etkinleştirilemedi',str(e))

    def rollback_rule(self):
        if not messagebox.askyesno('Çekirdek rol talimatını geri al','Bir önceki kayıtlı çekirdek talimat sürümüne dönülsün mü? Kod ve oyun dosyaları değişmez.'):return
        try:
            version=brain.rollback_previous_policy()
            self.log('Talimat rollback tamamlandı: v'+str(version))
            self.refresh_council()
        except Exception as e:messagebox.showerror('Geri alma başarısız',str(e))

    def prepare_candidate(self):
        try:
            path=evolution.create_candidate(self.core_goal.get('1.0','end').strip())
            self.v_candidate.set(str(path))
            self.log('Çekirdek yedek denemesi hazır: '+str(path))
            messagebox.showinfo('Deneme hazır','Canlı stüdyo değişmedi.\n'+str(path))
        except Exception as e:messagebox.showerror('Aday oluşturulamadı',str(e))

    def code_candidate(self):
        candidate=self.v_candidate.get()
        if not candidate:messagebox.showinfo('Önce kopya','Önce çekirdek deneme kopyası oluştur.');return
        if not messagebox.askyesno('AI ile aday kodlama','Codex yalnızca çekirdeğin AYRI kopyasında kod yazacak. AI kotası kullanılır. Onaylıyor musun?'):return
        def worker():
            self.log('Codex çekirdeğin deneme kopyasını düzenliyor...')
            m=evolution.run_candidate_coder(candidate)
            self.log('Kodlama durumu: '+m['state']+' '+str(m.get('ai_result'))[-350:])
        self.run_background(worker)

    def audit_candidate(self):
        candidate=self.v_candidate.get()
        if not candidate:messagebox.showwarning('Önce kopya','Deneme kopyası yok.');return
        if not messagebox.askyesno('Çekirdek regresyonu ve AI denetimi','Önce tüm yerel testler çalıştırılacak. Geçerse Claude ve Gemini iki ayrı AI incelemesi yapacak. Devam mı?'):return
        def worker():
            results=evolution.regression_gate(candidate)
            self.log('Regresyon testi: '+str(results)[:600])
            if not results['ok']:return
            for provider in ('Claude','Gemini'):
                self.log(provider+' çekirdek kod farkını bağımsız denetliyor...')
                evolution.inspect_candidate(candidate,provider)
            if evolution.ready_to_export(candidate):
                target=evolution.export_candidate(candidate)
                self.log('Test + iki AI onaylı deneme paketi: '+str(target))
                self.after(0,lambda:messagebox.showinfo('Deneme tamam','Yeni çekirdek adayı kontrol edilebilir ZIP olarak hazır. Çalışan stüdyo kendiliğinden değişmedi.\n'+str(target)))
            else:self.log('Denetim reddedildi veya yüksek risk tespit edildi. Canlı çekirdek korunuyor.')
        self.run_background(worker)

    def install_candidate(self):
        candidate=self.v_candidate.get()
        if not candidate:messagebox.showwarning('Kopya seç','Önce aday çekirdek oluştur.');return
        if not messagebox.askyesno('ÖNEMLİ: Çekirdek kodu değişecek',
            'Bu işlem çalışan stüdyonun Python dosyalarını değiştirecek. Yalnızca tüm testleri ve iki AI incelemesini geçen denemeler uygulanabilir. Yerel yedek oluşturulur. Oyun depolarınız değiştirilmez.\n\nKurulum için gerçekten onaylıyor musun?'):return
        try:
            info=evolution.install_approved_candidate(candidate,owner_approved=True)
            self.log('Onaylı çekirdek kuruldu: '+str(info))
            messagebox.showinfo('Kurulum tamam','Çekirdek güncellendi ve yedeklendi. Değişikliklerin yüklenmesi için stüdyoyu kapatıp yeniden aç.\nYedek: '+info['backup'])
        except Exception as e:messagebox.showerror('Kod kurulamadı',str(e))

    def rollback_code(self):
        if not messagebox.askyesno('Çekirdek kodunu geri al','Son uygulanan çekirdek kod değişikliği yedekten geri alınacak. Onaylıyor musun?'):return
        try:
            info=evolution.rollback_latest_code()
            self.log('Çekirdek kodu geri alındı: '+str(info))
            messagebox.showinfo('Geri alındı','Önceki çekirdek dosyaları geri yüklendi. Stüdyoyu kapatıp yeniden aç.')
        except Exception as e:messagebox.showerror('Geri alınamadı',str(e))

    def scan_radar(self):
        def worker():
            result=brain.radar_check()
            self.log(f"Radar tamamlandı: {len(result['releases'])} sürüm, {len(result['errors'])} erişim hatası")
            self.after(0,self.show_radar)
        self.run_background(worker)

    def ai_radar(self):
        if not messagebox.askyesno('Tek AI çağrısı','Resmî sürüm bilgilerini AI ile değerlendirmek için 1 AI çağrısı yapılacak. Yükleme veya güncelleme yapılmaz. Devam mı?'):return
        def worker():
            result=brain.analyze_radar_with_ai()
            self.log('Radar AI fırsat raporu: '+result['summary'])
            self.after(0,self.show_radar)
        self.run_background(worker)

    def show_radar(self):
        if not hasattr(self,'radar_output'):return
        self.radar_output.delete('1.0','end')
        self.radar_output.insert('1.0',brain.radar_report()+'\n\nAI FIRSAT DEĞERLENDİRMESİ\n'+brain.radar_ai_report())

    def _company(self):
        p=self._inner(self.p_company)
        self.header(p,'AI Sirket Merkezi · Sen son onay makamisin',
          'Yonetim kurulu, Ar-Ge, maliyet ve gelir onerileri. AI karar raporu verir; satin alma, kod dagitimi ve yayim yapmaz.')
        self.lbl(p,'Sirket hedefin veya yeni fikrin','H2.TLabel').pack(anchor='w',pady=(8,3))
        self.ceo_goal=self.text(p,4)
        self.ceo_goal.insert('1.0','Kucuk bir MVP yapip kullanici geri bildirimi ve gelir modeli denemek istiyorum.')
        row=ttk.Frame(p);row.pack(anchor='w',pady=7)
        self.btn(row,'Toplanti gundemi olustur (0 AI)',lambda:self.company_meeting(False))
        self.btn(row,'Claude + Gemini kurul gorusu (2 AI)',lambda:self.company_meeting(True))
        row=ttk.Frame(p);row.pack(anchor='w')
        self.lbl(row,'Ollama modeli:').pack(side='left',padx=(0,7))
        ttk.Entry(row,textvariable=self.v_ollama_model,width=20).pack(side='left',padx=(0,8))
        self.btn(row,'Yerel ucretsiz modelden gorus al',self.company_ollama)
        self.hint(p,'Toplanti baslatilinca en fazla iki bagimsiz AI calisir. Abonelik sinirlari ile gunluk kota korunur.')
        self.lbl(p,'Altyapi ve abonelik kararlari','H2.TLabel').pack(anchor='w',pady=(12,2))
        row=ttk.Frame(p);row.pack(anchor='w')
        ttk.Combobox(row,textvariable=self.v_server,values=['web','mobile','game','realtime'],width=16,state='readonly').pack(side='left',padx=(0,9))
        self.btn(row,'Sunucu secenekleri icin oneri uret',self.company_server)
        self.btn(row,'Ucretsiz AI katalogu',self.company_free)
        self.lbl(p,'Yeni bir uyelik gercekten deger mi? (aylik senaryo)','H2.TLabel').pack(anchor='w',pady=(12,3))
        row=ttk.Frame(p);row.pack(anchor='w')
        self.lbl(row,'Uyelik:').pack(side='left')
        ttk.Entry(row,textvariable=self.v_subname,width=19).pack(side='left',padx=(4,10))
        self.lbl(row,'USD/ay:').pack(side='left')
        ttk.Entry(row,textvariable=self.v_subcost,width=7).pack(side='left',padx=(4,9))
        self.lbl(row,'Saat/ay:').pack(side='left')
        ttk.Entry(row,textvariable=self.v_subhours,width=7).pack(side='left',padx=(4,9))
        self.lbl(row,'Saat degeri:').pack(side='left')
        ttk.Entry(row,textvariable=self.v_hourvalue,width=7).pack(side='left',padx=(4,8))
        self.btn(row,'Faydayi hesapla',self.company_subscription)
        self.lbl(p,'Karar ve onay bekleyen oneri','H2.TLabel').pack(anchor='w',pady=(12,2))
        self.company_recs=ttk.Treeview(p,columns=('category','status','price'),show='headings',height=5)
        for c,title,size in [('category','Tip',125),('status','Durum',210),('price','Fiyat bilgisi',210)]:
            self.company_recs.heading(c,text=title);self.company_recs.column(c,width=size)
        self.company_recs.pack(fill='x',pady=6)
        row=ttk.Frame(p);row.pack(anchor='w')
        self.btn(row,'Oneriyi onayla (islem yapmaz)',lambda:self.company_decide(True))
        self.btn(row,'Reddet',lambda:self.company_decide(False))
        self.btn(row,'Onerileri yenile',self.company_refresh)
        self.hint(p,'Onay kaydi satin alma, sunucu olusturma, core kod degisimi veya dagitim GERCEKLESTIRMEZ.')
        self.lbl(p,'Kurul raporu ve tavsiyeler','H2.TLabel').pack(anchor='w',pady=(9,2))
        self.company_output=self.text(p,12)
        self.company_output.insert('1.0','Kurul toplantisi icin yukarida hedef yaz. Yeni hesaplari kendin acman gerekir.')
        self.company_refresh()

    def company_refresh(self):
        if not hasattr(self,'company_recs'):return
        self.company_recs.delete(*self.company_recs.get_children())
        for item in company.recommendations()[-35:]:
            price=('fiyat yeniden dogrula' if item.get('price') is None else str(item['price'])+' '+item.get('currency',''))
            self.company_recs.insert('','end',iid=item['id'],values=(item['category'],item['status'],price),text=item['title'])

    def company_show(self,text):
        self.company_output.delete('1.0','end');self.company_output.insert('1.0',text)

    def company_meeting(self,with_ai):
        goal=self.ceo_goal.get('1.0','end').strip()
        if with_ai and not messagebox.askyesno('AI toplantisi',
            'Bu toplantida iki farkli AI (Claude + Gemini) tek tek cagrilacak. Gunluk abonelik kotan tuketilir. Devam?'):return
        def work():
            report=company.meet(goal,with_ai=with_ai)
            text=company.export_report(report)
            self.after(0,lambda:self.company_show(text))
            self.log('Yonetim kurulu raporu olusturuldu: '+report['id'])
        self.run_background(work)

    def company_ollama(self):
        goal=self.ceo_goal.get('1.0','end').strip();model=self.v_ollama_model.get().strip()
        def work():
            result=company.local_ollama_opinion(goal,model)
            self.after(0,lambda:self.company_show(result['output']))
            self.log('Ollama: '+('gorus alindi' if result['ok'] else 'baglanti olmadi'))
        self.run_background(work)

    def company_server(self):
        try:
            item=company.suggest_infrastructure(self.v_server.get())
            self.company_show('Sunucu onerisi: '+item['title']+'\n\n'+item['reason']+'\n\nResmi fiyat: '+item['source_url']+
                '\n\nDurum: SADECE ONERI. Satin alma yapilmadi.')
            self.company_refresh()
        except Exception as e:messagebox.showerror('Onermede sorun',str(e))

    def company_free(self):
        options=company.free_candidates()
        self.company_show('\n\n'.join(x['name']+'\nKullanim: '+x['reason']+'\nSinir: '+x['limitations']+'\nKaynak: '+x['url'] for x in options))

    def company_subscription(self):
        try:
            name=self.v_subname.get().strip()
            if len(name)<5:raise ValueError('Uyelik adini yaz')
            price=float(self.v_subcost.get().replace(',','.'))
            hours=float(self.v_subhours.get().replace(',','.'))
            worth=float(self.v_hourvalue.get().replace(',','.'))
            result=company.cost_evaluation(price,hours,worth)
            item=company.recommend('subscription','Uyelik analizi: '+name,
               'KULLANICI VARSAYIMI: Tahmini '+str(hours)+' saat/ay tasarruf, '+str(worth)+
               ' USD/saat. Hesaplanan net fayda: '+str(result['estimated_net'])+
               ' USD/ay. Hiz, dogruluk, fatura/vergi ve API farki ayrica gercek verilerle olculmeli.',
               price=price,currency='USD',home=None)
            self.company_show('Uyelik: '+name+'\n'+str(result)+'\n\nBu hesap gelir garantisi degildir.\n'+
                'Uyeligi acmadan once resmi fiyati dogrula. Onay kaydi odeme yapmaz.')
            self.company_refresh()
        except Exception as e:messagebox.showwarning('Gecersiz veri',str(e))

    def company_decide(self,approved):
        rows=self.company_recs.selection()
        if not rows:messagebox.showinfo('Secim gerekli','Bir tavsiye satiri sec.');return
        rid=rows[0]
        if not messagebox.askyesno('Sahip onayi',
          ('Bu karari ONAYLAYACAKSIN.' if approved else 'Bu karari REDDEDECEKSIN.')+
          '\nKayit disinda satin alma, hesap acma, kod veya sistem degisikligi yapilmayacak.'):return
        try:
            item=company.decide(rid,approved)
            self.company_refresh()
            self.company_show(item['title']+'\nDurum: '+item['status']+
                 '\nBir sonraki islem icin ayri ve acik onay gerekir.')
        except Exception as e:messagebox.showerror('Karar hatasi',str(e))

    def _projects(self):
        p=self._inner(self.p_proj)
        self.header(p,'Tüm oyunların ve uygulamaların','Projeler birbirinden bağımsızdır. Ortak çekirdek, doğrulanmış dersleri proje bazında karşılaştırır.')
        self.lbl(p,'Kayıtlı projeler — çift tıkla ve aktif projeyi değiştir','H2.TLabel').pack(anchor='w',pady=(8,4))
        self.project_tree=ttk.Treeview(p,columns=('name','engine','path'),show='headings',height=5)
        for key,title,w in [('name','Proje',180),('engine','Motor',100),('path','Klasör',550)]:
            self.project_tree.heading(key,text=title);self.project_tree.column(key,width=w)
        self.project_tree.pack(fill='x',pady=(0,7))
        self.project_tree.bind('<Double-1>',lambda e:self.switch_project())
        row=ttk.Frame(p);row.pack(anchor='w',pady=3)
        self.btn(row,'Seçilen projeye geç',self.switch_project)
        self.btn(row,'Listeyi yenile',self.refresh_project_list)
        self.lbl(p,'Yeni proje ekle veya bağla','H2.TLabel').pack(anchor='w',pady=(12,4))
        self.formrow(p,'Proje adı',self.v_name)
        self.lbl(p,'Motor','H2.TLabel').pack(anchor='w',pady=(10,4))
        pick=ttk.Combobox(p,textvariable=self.v_engine,values=list(core.ENGINE_LABELS),state='readonly')
        pick.pack(fill='x')
        self.formrow(p,'Projelerin saklanacağı klasör',self.v_root)
        row=ttk.Frame(p);row.pack(anchor='w')
        self.btn(row,'Klasör seç',self.pick_root)
        self.lbl(p,'Oyun / uygulama fikrini birkaç cümleyle anlat','H2.TLabel').pack(anchor='w',pady=(8,3))
        self.idea=self.text(p,5)
        row=ttk.Frame(p);row.pack(anchor='w',pady=4)
        self.btn(row,'Yeni proje oluştur',self.new_project)
        self.btn(row,'Mevcut projeyi bağla',self.attach)
        self.btn(row,'Klasörü aç',self.open_project)
        self.hint(p,'Unity, Unreal ve Kotlin projeleri için önce ilgili editörden boş proje açılır; mevcut proje tek tıkla stüdyoya bağlanır.')

    def _agents(self):
        p=self._inner(self.p_agent)
        self.header(p,'AI Geliştirme Ekibi','Projeyi bir defa bağla; küçük görevlerle kodla. Her görevde sağlayıcıya otomatik veya manuel karar ver.')
        self.lbl(p,'Yapılacak işi yaz','H2.TLabel').pack(anchor='w',pady=(9,3))
        self.task=self.text(p,5)
        self.lbl(p,'Görev türü','H2.TLabel').pack(anchor='w',pady=(8,3))
        ttk.Combobox(p,textvariable=self.v_kind,values=['Yeni ozellik / Kod','Hata duzeltme','Mimari / Plan','Inceleme / Analiz','Tasarim karari'],state='readonly').pack(fill='x')
        row=ttk.Frame(p);row.pack(fill='x',pady=(10,0))
        self.lbl(row,'AI seçimi:').pack(side='left',padx=(0,8))
        ttk.Combobox(row,textvariable=self.v_provider,values=['Otomatik','Claude','Codex','Gemini'],width=16,state='readonly').pack(side='left',padx=(0,22))
        self.lbl(row,'Kalite:').pack(side='left',padx=(0,8))
        ttk.Combobox(row,textvariable=self.v_quality,values=['Ekonomik','Dengeli','En guclu'],width=16,state='readonly').pack(side='left')
        row2=ttk.Frame(p);row2.pack(anchor='w',pady=(14,0))
        self.lbl(row2,'Günlük görev sınırı:').pack(side='left',padx=(0,6))
        ttk.Spinbox(row2,from_=1,to=30,width=6,textvariable=self.v_day).pack(side='left',padx=(0,25))
        self.lbl(row2,'Görev başına süre (dk):').pack(side='left',padx=(0,6))
        ttk.Spinbox(row2,from_=2,to=45,width=6,textvariable=self.v_mins).pack(side='left')
        row3=ttk.Frame(p);row3.pack(anchor='w',pady=10)
        self.btn(row3,'Tek görev çalıştır',self.start_task)
        self.btn(row3,'Plan + Kod + Test otomatik',self.start_guided)
        self.btn(row3,'Model planını göster',self.show_route)
        self.btn(row3,'Olculen AI verimliligi',self.show_performance)
        self.count_label=self.lbl(p,'','Dim.TLabel');self.count_label.pack(anchor='w')
        self.hint(p,'İlgili AI hesabında giriş gerekli. Dosya değişikliği yapılmadan önce yedek veya Git kontrol noktası önerilir. İşlem başarısızsa otomatik sonsuz tekrar yapılmaz.')

    def _queue_tab(self):
        p=self._inner(self.p_queue)
        self.header(p,'AI Görev Merkezi',
                    'Çoklu proje, tek onaylı AI işi. Görevler kalıcıdır; başlatma ve sonuç kabulü ayrı işlemdir.')
        self.hint(p,'AI Ekibi sekmesindeki görev metnini bu kuyruğa ekle. Önce ilgili projeyi seç.')
        row=ttk.Frame(p);row.pack(anchor='w',pady=6)
        self.lbl(row,'Öncelik:').pack(side='left')
        ttk.Spinbox(row,from_=1,to=5,width=5,textvariable=self.v_queue_priority).pack(side='left',padx=8)
        self.btn(row,'Görevi kuyruğa ekle',self.queue_add)
        columns=('code','status','priority','project','provider','title')
        self.queue_table=ttk.Treeview(p,columns=columns,show='headings',selectmode='browse',height=10)
        for col,label,width in [('code','Kod',110),('status','Durum',145),
                                ('priority','Öncelik',75),('project','Proje',130),
                                ('provider','AI',85),('title','Görev',335)]:
            self.queue_table.heading(col,text=label)
            self.queue_table.column(col,width=width,stretch=(col=='title'))
        self.queue_table.pack(fill='both',expand=True,pady=6)
        self.queue_table.bind('<<TreeviewSelect>>',self.queue_selection)
        controls=ttk.Frame(p);controls.pack(anchor='w',pady=4)
        self.btn(controls,'Yenile',self.queue_refresh)
        self.btn(controls,'AI seçimi / limit önizleme',self.queue_preview)
        self.btn(controls,'Onayla',self.queue_approve)
        self.btn(controls,'Onaylı tek görevi çalıştır',self.queue_run)
        row=ttk.Frame(p);row.pack(anchor='w',pady=4)
        self.btn(row,'Oynanışı kabul et',self.queue_accept)
        self.btn(row,'Düzeltme iste',self.queue_reject)
        self.btn(row,'Yeni onay iste',self.queue_retry)
        self.btn(row,'İptal et',self.queue_cancel)
        self.btn(row,'Yarım kalan işi kurtar',self.queue_recover)
        self.queue_info=self.lbl(p,'','Dim.TLabel');self.queue_info.pack(anchor='w',pady=4)
        self.hint(p,'Kuyruk kendi başına AI çalıştırmaz. Gerçek token kotası bilinmez. Kodlama CLI erişim sınırları ayrıca geçerlidir.')
        self.queue_refresh()

    def queue_selection(self,_event=None):
        selected=self.queue_table.selection()
        if selected:self.v_queue_id.set(selected[0])

    def queue_refresh(self):
        selected=self.v_queue_id.get()
        for item in self.queue_table.get_children():self.queue_table.delete(item)
        for item in task_queue.list_tasks():
            self.queue_table.insert('','end',iid=item['id'],values=(
                item['id'],item['status'],item['priority'],Path(item['project']).name,
                item['provider_preference'],item['title'][:115]))
        if selected in self.queue_table.get_children():self.queue_table.selection_set(selected)
        counts=task_queue.statistics()
        self.queue_info.configure(text=str(counts['status'])+' | Bugün yerel AI çağrısı: '+str(counts['calls_today_local']))

    def queue_id(self):
        ident=self.v_queue_id.get()
        if not ident:raise ValueError('Önce listeden bir görev seç')
        return ident

    def queue_add(self):
        try:
            project=self.active()
            if not project:return
            item=task_queue.add_task(project,self.task.get('1.0','end').strip(),self.v_kind.get(),
                self.v_provider.get(),self.v_quality.get(),int(self.v_queue_priority.get()),int(self.v_mins.get()))
            self.v_queue_id.set(item['id']);self.queue_refresh()
            self.log('Onay bekleyen görev: '+item['id'])
        except Exception as err:messagebox.showerror('Görev eklenemedi',str(err))

    def queue_preview(self):
        try:
            r=task_queue.preview_next(int(self.v_day.get()))
            if not r['ready']:messagebox.showinfo('Kuyruk','Onaylı görev yok');return
            messagebox.showinfo('AI / Limit önizlemesi',
                f"Proje: {r['project']}\nTahmini AI: {r['provider_estimate']} ({r['model_estimate']})\n"
                f"Süre sınırı: {r['max_minutes']} dakika\nBeklenen CLI çağrısı: 1\n"
                f"Bugün: {r['local_calls_today']}/{r['day_limit']}\n"
                f"Başlatma engeli: {r['blocked']}\n\n{r['note']}")
        except Exception as err:messagebox.showerror('Önizleme hatası',str(err))

    def queue_approve(self):
        try:
            ident=self.queue_id()
            if not messagebox.askyesno('Sahip onayı','Seçili AI görevini çalışmaya hazır olarak onaylıyor musun?'):
                return
            task_queue.approve(ident);self.queue_refresh()
        except Exception as err:messagebox.showerror('Onay hatası',str(err))

    def queue_run(self):
        if not messagebox.askyesno('Kullanım hakkı uyarısı',
            'Sıradaki ONAYLANMIŞ işi tek AI çağrısıyla başlatacağız. Abonelik kotası tüketilebilir. Devam?'):return
        def worker():
            item=task_queue.execute_one(int(self.v_day.get()),on_update=self.log)
            self.log('Kuyruk: '+(item['id']+' '+item['status'] if item else 'Onaylı görev yok'))
            self.after(0,self.queue_refresh)
        self.run_background(worker)

    def queue_accept(self):
        try:
            ident=self.queue_id()
            if not messagebox.askyesno('Oynanış / UI kontrolü',
                'Oyunu veya uygulamayı açıp bizzat kontrol ettin ve sonucu kabul ediyor musun?'):return
            task_queue.accept(ident);self.queue_refresh()
        except Exception as err:messagebox.showerror('Kabul hatası',str(err))

    def queue_reject(self):
        try:
            ident=self.queue_id()
            from tkinter import simpledialog
            reason=simpledialog.askstring('Düzeltme iste','Düzeltilmesini istediğin yer nedir?')
            if reason is None:return
            task_queue.request_rework(ident,reason);self.queue_refresh()
        except Exception as err:messagebox.showerror('Düzeltme hatası',str(err))

    def queue_retry(self):
        try:
            ident=self.queue_id()
            if not messagebox.askyesno('Yeniden onay','Bu görevi yeniden onay kuyruğuna alalım mı? Otomatik çalışmayacak.'):return
            task_queue.reset_for_manual_retry(ident);self.queue_refresh()
        except Exception as err:messagebox.showerror('Yeni onay hatası',str(err))

    def queue_cancel(self):
        try:
            ident=self.queue_id()
            if not messagebox.askyesno('İptal','Görevi iptal etmek istiyor musun?'):return
            task_queue.cancel(ident);self.queue_refresh()
        except Exception as err:messagebox.showerror('İptal hatası',str(err))

    def queue_recover(self):
        try:
            ident=self.queue_id()
            if not messagebox.askyesno('Kurtarma onayı',
                'Yalnızca ilgili AI işleminin artık ÇALIŞMADIĞINDAN EMİNSEN onayla. Otomatik tekrar yapılmayacak.'):return
            task_queue.recover_interrupted(ident,confirm=True);self.queue_refresh()
        except Exception as err:messagebox.showerror('Kurtarma hatası',str(err))

    def _testing(self):
        p=self._inner(self.p_test)
        self.header(p,'Kalite kontrol ve öğrenme','Oyun motoruna göre doğrula; hatalar kalıcı notlara yazılır. Oynanış ve görsel sonuç kontrolü sende.')
        row=ttk.Frame(p);row.pack(anchor='w',pady=10)
        self.btn(row,'Yerel testleri çalıştır',self.start_test)
        self.btn(row,'Kod yedeği oluştur',self.backup_now)
        self.btn(row,'Dersler dosyasını aç',self.open_lessons)
        self.btn(row,'İlerleme dosyasını aç',self.open_progress)
        self.btn(row,'Oyunda kontrol ettim, onayla',self.manual_approve)
        self.hint(p,'Unity/Unreal testleri yalnızca motor kurulu ve sürüme uygun otomasyon hazırsa mümkündür. Bu ilk sürüm motor bulunmayan makinede test geçmiş gibi davranmaz.')
        self.results=self.text(p,13)

    def _assets(self):
        p=self._inner(self.p_assets)
        self.header(p,'Görsel üretim atölyesi','2D: ChatGPT/Gemini. 3D: yalnızca Meshy. Pro üyeliklerinin görsel arayüzleri otomatik API değildir.')
        self.lbl(p,'Üretim türü','H2.TLabel').pack(anchor='w',pady=(10,4))
        ttk.Combobox(p,textvariable=self.v_asset,values=['2D','3D'],state='readonly').pack(fill='x')
        self.lbl(p,'İstediğin varlığı tarif et','H2.TLabel').pack(anchor='w',pady=(10,4))
        self.assetdesc=self.text(p,5)
        row=ttk.Frame(p);row.pack(anchor='w',pady=8)
        self.btn(row,'Üretim talimatını hazırla/kopyala',self.asset_prompt)
        self.btn(row,'ChatGPT aç',lambda:webbrowser.open('https://chatgpt.com/'))
        self.btn(row,'Gemini aç',lambda:webbrowser.open('https://gemini.google.com/'))
        self.btn(row,'Meshy aç',lambda:webbrowser.open('https://www.meshy.ai/'))
        self.hint(p,'Ürettiğin 2D varlıkları projenin assets/2d, 3D varlıkları assets/3d klasörüne kaydet. Bu butonlar otomatik görsel üretimi yapmaz.')

    def _github(self):
        p=self._inner(self.p_git)
        self.header(p,'GitHub Actions ve depolar','Her push/PR için temel kontrol ve haftalık sağlık raporu. AI modellerini GitHub sunucusuna bağlamaz.')
        self.hint(p,'Önce bir proje bağla. Mevcut GitHub workflow dosyalarının üstüne yazılmaz.')
        row=ttk.Frame(p);row.pack(anchor='w',pady=12)
        self.btn(row,'Actions dosyalarını projeye ekle',self.github_actions)
        self.btn(row,'GitHub hesabına giriş',lambda:self.terminal(['gh','auth','login']))
        row=ttk.Frame(p);row.pack(anchor='w')
        self.btn(row,'GitHub deposu oluştur/yayınla',self.github_publish)
        self.btn(row,'Depo klasörünü aç',self.open_project)
        self.hint(p,'GitHub yayınlama yalnızca kullanıcı onayıyla yapılır. Workflowlar secrets kullanmaz ve otomatik merge/push yapmaz.')

    def _system(self):
        p=self._inner(self.p_sys)
        self.header(p,'Kurulum ve bağlantı durumları','Önce yalnızca gerekli araçları kur. Bozuk winget zorunlu değil; kurulum resmî kaynakları gösterir.')
        row=ttk.Frame(p);row.pack(anchor='w',pady=5)
        self.btn(row,'Yeniden kontrol et',self.refresh)
        self.btn(row,'Kurulum kılavuzunu aç',self.open_guide)
        self.sysinfo=self.text(p,15)
        row=ttk.Frame(p);row.pack(anchor='w')
        self.btn(row,'Claude giriş',lambda:self.terminal(['claude']))
        self.btn(row,'Codex giriş',lambda:self.terminal(['codex','login']))
        self.btn(row,'Gemini giriş',lambda:self.terminal(['gemini']))
        installers=ttk.Frame(p);installers.pack(anchor='w',pady=(8,0))
        self.btn(installers,'Git indir',lambda:webbrowser.open(core.LINKS['Git']))
        self.btn(installers,'GitHub CLI indir',lambda:webbrowser.open(core.LINKS['GitHub CLI']))
        self.btn(installers,'Godot indir',lambda:webbrowser.open(core.LINKS['Godot']))
        self.btn(installers,'Flutter rehberi',lambda:webbrowser.open(core.LINKS['Flutter']))
        self.btn(installers,'Android Studio',lambda:webbrowser.open(core.LINKS['Android Studio']))
        self.hint(p,'Önce terminalde ilgili uygulamanın hesap girişini tamamla. API anahtarı istenmez ve kayıt altına alınmaz.')

    def refresh_project_list(self):
        if not hasattr(self,'project_tree'):return
        for item in self.project_tree.get_children():self.project_tree.delete(item)
        active=core.active_project()
        for path,item in sorted(brain.list_projects().items(),key=lambda r:r[1]['name'].lower()):
            self.project_tree.insert('', 'end',iid=path,values=(item['name'],item['engine'],path))
        if active and str(active) in self.project_tree.get_children():self.project_tree.selection_set(str(active))

    def switch_project(self):
        rows=self.project_tree.selection()
        if not rows:messagebox.showinfo('Proje seç','Listeden bir proje seçin.');return
        core.set_active(rows[0]);self.load_state()
        self.log('Aktif proje değiştirildi: '+rows[0])

    def load_state(self):
        self.refresh_project_list()
        active=core.active_project()
        if active:self.v_proj.set('Aktif proje: '+str(active)+'  •  '+core.project_type(active))
        self.count_label.configure(text=f'Bugün kullanılan yerel AI görevleri: {core.usage_count()} / {self.v_day.get()}')
    def active(self):
        p=core.active_project()
        if not p: messagebox.showwarning('Proje gerekli','Önce Projeler sekmesinden bir proje oluştur veya bağla.')
        return p
    def pick_root(self):
        path=filedialog.askdirectory(title='Projelerin saklanacağı klasör')
        if path:self.v_root.set(path)
    def new_project(self):
        try:
            p=core.create_project(self.v_root.get(),self.v_name.get(),self.v_engine.get(),self.idea.get('1.0','end'))
            core.set_active(p);self.load_state();self.log('Yeni proje: '+str(p))
            messagebox.showinfo('Proje hazır','Proje oluşturuldu:\n'+str(p)+'\n\nAI Ekibi sekmesinden ilk görevini yazabilirsin.')
        except Exception as e:messagebox.showerror('Proje oluşturulamadı',str(e))
    def attach(self):
        d=filedialog.askdirectory(title='Mevcut oyun veya uygulama projesini seç')
        if not d:return
        try:
            p,engine=core.attach_project(d,self.idea.get('1.0','end'))
            core.set_active(p);self.load_state();self.log('Bağlandı: '+str(p)+' ('+engine+')')
        except Exception as e:messagebox.showerror('Bağlantı sorunu',str(e))
    def open_dir(self,path):
        if not Path(path).exists():return
        if sys.platform=='win32':os.startfile(str(path))
        elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
        else:subprocess.Popen(['xdg-open',str(path)])
    def open_project(self):
        p=self.active()
        if p:self.open_dir(p)
    def open_lessons(self):
        p=self.active()
        if p:self.open_dir(p/'.studio')
    def open_progress(self):self.open_lessons()
    def run_background(self,fn):
        if self.busy:messagebox.showwarning('İşlem sürüyor','Bir işlem sürerken yeni AI/test başlatılmaz.');return
        self.busy=True
        def work():
            try:fn()
            except Exception as e:
                self.log('HATA: '+str(e));self.after(0,lambda err=str(e):messagebox.showerror('İşlem başarısız',err))
            finally:self.after(0,self.release)
        threading.Thread(target=work,daemon=True).start()
    def release(self):self.busy=False;self.load_state()
    def suggest_step(self):
        p=self.active()
        if not p:return
        number,detail=core.next_step(p)
        if not messagebox.askyesno('Sıradaki adım',f'Aşama {number}:\n\n{detail}\n\nBu görevi AI Ekibi sayfasına kopyalayayım mı?'):return
        self.task.delete('1.0','end');self.task.insert('1.0',detail)
        self.tabs.select(self.p_agent)
    def manual_approve(self):
        p=self.active()
        if not p:return
        number,detail=core.next_step(p)
        if not messagebox.askyesno('Manuel oyun/uygulama onayı',f'Aşama {number}:\n{detail}\n\nBu aşamayı gerçekten oyunda/uygulamada test edip onaylıyor musun?'):return
        try:
            num,nextdetail=core.approve_step(p)
            self.log(f'Kullanıcı aşama {number} onayı kaydedildi. Sıradaki: {num}: {nextdetail}')
            messagebox.showinfo('Onay kaydedildi',f'Sıradaki aşama {num}:\n{nextdetail}')
        except Exception as e:messagebox.showerror('Onay sorunu',str(e))
    def show_performance(self):
        stats=company.provider_performance()
        if not stats:
            messagebox.showinfo('AI verimliligi','Henuz gercekten dogrulanmis yeterli gorev yok. Kullanilan aboneliklerin kalan tokenlarini okuyamiyoruz.');return
        lines=['Yalnizca motor testiyle dogrulanmis gorev basarisi. Token/para tuketimi olculmuyor.']
        for provider,d in sorted(stats.items()):
            score=('-' if d['success_rate'] is None else str(round(100*d['success_rate']))+'%')
            lines.append(f"{provider}: {d['observed']} dogrulama, basari {score}, karsilastirma icin yeterli: {d['enough_for_comparison']}")
        messagebox.showinfo('AI performans raporu','\n'.join(lines))

    def show_route(self):
        pr,model=core.route(self.v_kind.get(),self.v_provider.get(),self.v_quality.get())
        messagebox.showinfo('Görev yönlendirmesi',f'AI: {pr}\nModel: {model}\n\nOtomatik seçim yerel kurallara dayanır. Gerçek kalan sağlayıcı kotası API üzerinden okunmuyor.')
    def start_task(self):
        p=self.active()
        if not p:return
        kind=self.v_kind.get();description=self.task.get('1.0','end').strip()
        if not description:messagebox.showinfo('Görev gerekli','Yapılacak işi yaz.');return
        pr,model=core.route(kind,self.v_provider.get(),self.v_quality.get())
        if not messagebox.askyesno('AI görevi çalıştır',f'{pr} • {model}\n\nProje: {p}\n\nGörev: {description[:200]}\n\nKod değişiklikleri yapabilir. Git commit/yedek kontrolünü öneriyoruz. Onaylıyor musun?'):return
        def worker():
            result=core.run_ai_task(p,kind,description,self.v_provider.get(),self.v_quality.get(),int(self.v_day.get()),int(self.v_mins.get()),on_update=self.log)
            self.log('SONUÇ: '+('Test geçti' if result['success'] else 'Kullanıcı kontrolü / ek düzeltme gerekli'))
            self.log(result['output'][-1500:]);self.log(result['test_report'][-1400:])
            if not result['success']:
                try:
                    outcome=brain.auto_council_once(day_limit=int(self.v_day.get()),report=self.log)
                    if outcome['status'] not in ('disabled','deferred'):
                        self.log('AI Çekirdek Konseyi sonucu: '+str(outcome)[:450])
                except Exception as e:self.log('AI Konsey durduruldu: '+str(e)[:250])
            self.after(0,lambda:self.results.insert('end',result['test_report']+'\n'))
            self.after(0,lambda:messagebox.showinfo('Görev bitti','AI komutu bitti. Test raporunu incele ve oyunu/uygulamayı sen kontrol et.\n\n'+result['test_report'][:500]))
        self.run_background(worker)
    def start_guided(self):
        p=self.active()
        if not p:return
        description=self.task.get('1.0','end').strip()
        if not description:messagebox.showwarning('Gorev','Yapilacak isi yaz.');return
        n=3 if self.v_quality.get()=='En guclu' else 2
        if not messagebox.askyesno('Kontrollü otomatik iş akışı',f'{n} AI gorevi calisacak:\n1. Claude Sonnet plan\n2. Codex kod ve test\n'+('3. Gemini inceleme\n' if n==3 else '')+f'\nHer biri en fazla {self.v_mins.get()} dakika.\nSonsuz tekrar yok. Devam edilsin mi?'):return
        def worker():
            result=core.guided_workflow(p,description,self.v_quality.get(),int(self.v_day.get()),int(self.v_mins.get()),on_update=self.log)
            self.log('OTO AKIS: '+result['stage']+' - '+result['reason'][:1200])
            if not result['ok']:
                try:
                    outcome=brain.auto_council_once(day_limit=int(self.v_day.get()),report=self.log)
                    self.log('Çekirdek konseyi: '+str(outcome)[:400])
                except Exception as e:
                    self.log('AI çekirdek denetimi durdu: '+str(e)[:220])
            self.after(0,lambda:messagebox.showinfo('Oto akış tamamlandı' if result['ok'] else 'Oto akış durdu',result['reason'][:750]))
        self.run_background(worker)

    def backup_now(self):
        p=self.active()
        if not p:return
        try:
            target=core.backup_code(p)
            self.log('Kod dosyalari yerel yedeklendi: '+str(target))
            messagebox.showinfo('Kod yedeği',str(target)+'\n\nBüyük 3D/ses varlıkları bu küçük dosya yedeğine dahil edilmez.')
        except Exception as e:messagebox.showerror('Yedek sorunu',str(e))

    def start_test(self):
        p=self.active()
        if not p:return
        def worker():
            good,report=core.validate(p)
            self.log(report)
            self.after(0,lambda:self.results.insert('end',report+'\n\n'))
            if not good: self.log('Test geçmedi, kurulu değil veya motor özel doğrulama gerekiyor.')
            self.log('Motor testi sonucu: '+('GEÇTİ' if good else 'DOĞRULANAMADI'))
        self.run_background(worker)
    def asset_prompt(self):
        p=core.active_project();engine=core.project_type(p) if p else 'oyun/uygulama'
        try:
            prompt=core.create_asset_prompt(engine,self.assetdesc.get('1.0','end'),self.v_asset.get())
            self.clipboard_clear();self.clipboard_append(prompt)
            if p:
                dest=p/'.studio'/'ASSET_REQUESTS.md'
                with dest.open('a',encoding='utf-8') as f:f.write('\n## '+core.now()+' '+self.v_asset.get()+'\n\n'+prompt+'\n')
            messagebox.showinfo('Kopyalandı','Görsel üretim talimatı panoya kopyalandı. İlgili AI sitesine yapıştır.\n\n'+prompt[:430])
        except Exception as e:messagebox.showwarning('Eksik bilgi',str(e))
    def github_actions(self):
        p=self.active()
        if not p:return
        if not messagebox.askyesno('GitHub Actions','Bu projeye üç CI dosyası eklensin mi? Mevcut aynı isimli dosyalar korunacak.'):return
        try: self.log(core.add_ci(p));messagebox.showinfo('Hazır','Workflowlar eklendi. GitHub\'a push sonrası Actions başlayabilir.')
        except Exception as e:messagebox.showerror('CI hata',str(e))
    def terminal(self,cmd):
        actual=core.which(cmd[0])
        if not actual:messagebox.showwarning('Program bulunamadı',cmd[0]+' kurulu değil. Sistem sekmesinden bak.');return
        args=[actual]+cmd[1:]
        try:
            if sys.platform=='win32':subprocess.Popen(args,creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:subprocess.Popen(['x-terminal-emulator','-e']+args)
        except Exception as e:messagebox.showerror('Terminal açılamadı',str(e))
    def github_publish(self):
        p=self.active()
        if not p:return
        if not core.which('git') or not core.which('gh'):messagebox.showerror('Eksik program','Git ve GitHub CLI yüklü olmalı.');return
        if (p/'.git').exists():messagebox.showinfo('Mevcut depo','Bu projede zaten Git var. Otomatik yeniden depo kurulmaz. GitHub CLI ile mevcut depoyu elle bağlayabilirsin.');return
        if not messagebox.askyesno('GitHub özel depo oluşturma',f'Bu işlem gerçek GitHub hesabında ÖZEL depo oluşturacak ve proje dosyalarını gönderecek.\n\nProje: {p}\n\nSadece kendi dosyalarını GitHub\'a koymak istediğinden emin misin?'):return
        def worker():
            for cmd in [[core.which('gh'),'auth','status'],[core.which('git'),'init'],[core.which('git'),'add','.'],[core.which('git'),'commit','-m','Initial Ultra Pro Studio project'],[core.which('gh'),'repo','create',core.safe_name(p.name),'--private','--source','.','--remote','origin','--push']]:
                if cmd[1] in ('commit','repo'):
                    core.verify_git_publish_safe(p)
                r=core.run(cmd,p,timeout=120)
                self.log('$ '+' '.join(cmd[1:])+'\n'+r.stdout[-2000:])
                if r.returncode:raise RuntimeError('GitHub yayinlama durdu. Logu incele, hicbir komut sessizce atlanmadi.')
            self.after(0,lambda:messagebox.showinfo('GitHub','Özel depo oluşturuldu ve ilk push yapıldı.'))
        self.run_background(worker)
    def refresh(self):
        tools=core.tool_status()
        if not hasattr(self,'sysinfo'):return
        self.sysinfo.delete('1.0','end')
        for name,path in tools.items():
            self.sysinfo.insert('end',('✓ ' if path else '✕ ')+name+'\n    '+(str(path) if path else 'Kurulu değil / bulunamıyor')+'\n\n')
        self.log('Sistem programları tarandı. Eksik motorları yalnızca kullanacaksan kur.')
    def open_guide(self):self.open_dir(core.BASE/'KURULUM_VE_KULLANIM.md') if os.path.isfile(core.BASE/'KURULUM_VE_KULLANIM.md') else webbrowser.open('https://www.python.org/downloads/windows/')

if __name__=='__main__':Studio().mainloop()
