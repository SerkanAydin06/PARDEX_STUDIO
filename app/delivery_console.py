"""PARDEX single-goal delivery window: owner starts one native CLI, reviews diff."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import change_review
import core
import project_delivery


class DeliveryConsole(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('PARDEX • Tek Görev Teslimi')
        self.geometry('870x690')
        self.minsize(700, 580)
        self.project = tk.StringVar()
        self.goal = tk.StringVar(value='Oyuncuya ok tuşlarıyla hareket etme özelliği ekle')
        self.files = tk.StringVar(value='scripts/player.gd')
        self.provider = tk.StringVar(value='Codex')
        self.risk = tk.BooleanVar(value=False)
        self.review = None
        self.events = queue.Queue()
        self.working = False
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Tek Görev → AI Çalışma Kopyası → Test → Kod İncelemesi',
                  font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(0, 7))
        ttk.Label(frame, text='Gerçek proje, onayına kadar değişmez. Yerel AI CLI işletim sistemi sandbox’ı değildir.',
                  wraplength=760).pack(anchor='w', pady=(0, 12))
        project_row = ttk.Frame(frame)
        project_row.pack(fill='x', pady=3)
        ttk.Label(project_row, text='Oyun / uygulama klasörü:', width=25).pack(side='left')
        ttk.Entry(project_row, textvariable=self.project).pack(side='left', fill='x', expand=True)
        ttk.Button(project_row, text='Seç', command=self._browse).pack(side='left', padx=5)
        self._entry(frame, 'Yapılacak tek somut görev:', self.goal)
        self._entry(frame, 'Değiştirilebilecek dosyalar (virgülle):', self.files)
        chooser = ttk.Frame(frame)
        chooser.pack(fill='x', pady=7)
        ttk.Label(chooser, text='AI çalışan:', width=25).pack(side='left')
        ttk.Combobox(chooser, state='readonly', textvariable=self.provider,
                     values=['Codex', 'Claude', 'Gemini'], width=15).pack(side='left')
        ttk.Checkbutton(frame, variable=self.risk,
                        text='Yerel AI CLI’nin tam işletim sistemi izolasyonu olmadığını anlıyorum; bu tek çağrıya izin veriyorum.').pack(anchor='w', pady=6)
        actions = ttk.Frame(frame)
        actions.pack(fill='x', pady=12)
        self.preview_btn = ttk.Button(actions, text='Ücretsiz kontrol', command=self._preview)
        self.preview_btn.pack(side='left', padx=2)
        self.start_btn = ttk.Button(actions, text='Bu tek görevi çalıştır', command=self._start)
        self.start_btn.pack(side='left', padx=2)
        self.diff_btn = ttk.Button(actions, text='Kod farkını incele', command=self._diff, state='disabled')
        self.diff_btn.pack(side='left', padx=2)
        self.apply_btn = ttk.Button(actions, text='İncelenen kodu uygula', command=self._apply, state='disabled')
        self.apply_btn.pack(side='left', padx=2)
        self.status = ttk.Label(frame, text='Hazır. Önce ücretsiz kontrol yapabilirsin.', wraplength=760)
        self.status.pack(anchor='w', pady=5)
        self.output = tk.Text(frame, height=20, wrap='word', font=('Consolas', 10))
        self.output.pack(fill='both', expand=True)
        self.output.insert('end','Kod değişikliği ancak tam SHA256 incelemesi ve son onaydan sonra uygulanır.\n')
        self.output.config(state='disabled')
        self.after(120, self._poll)

    def _entry(self, frame, label, variable):
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text=label, width=36).pack(side='left')
        ttk.Entry(row, textvariable=variable).pack(side='left', fill='x', expand=True)

    def _browse(self):
        folder = filedialog.askdirectory(title='Godot / uygulama proje klasörü')
        if folder: self.project.set(folder)

    def _filenames(self):
        return [x.strip().replace('\\', '/') for x in self.files.get().split(',') if x.strip()]

    def _append(self, text):
        self.output.config(state='normal')
        self.output.insert('end', text + '\n')
        self.output.see('end')
        self.output.config(state='disabled')

    def _preview(self):
        try:
            info = project_delivery.preview(self.project.get(), self.goal.get(), self._filenames(),
                                            provider=self.provider.get())
            self._append('Ön kontrol: ' + info['engine'] + ' | ' + info['provider'] + ' | ' + ', '.join(info['expected_files']))
            self.status.config(text='Plan geçerli. Bu kontrol AI çağrısı yapmadı.')
        except Exception as error:
            messagebox.showerror('Ön kontrol başarısız', str(error))

    def _start(self):
        if self.working: return
        if not self.risk.get():
            messagebox.showwarning('Onay gerekli', 'Önce yerel CLI riskini anladığını onayla.')
            return
        try:
            project_delivery.preview(self.project.get(), self.goal.get(), self._filenames(),
                                     provider=self.provider.get())
        except Exception as error:
            messagebox.showerror('Görev geçersiz', str(error))
            return
        if not messagebox.askyesno('Tek AI çağrısı onayı',
                                   'Tek bir AI görevi çalışacak. Yerel CLI tam izole değildir ve hesabının kota kullanımını etkileyebilir. Devam?'):
            return
        self.review = None
        self.diff_btn.config(state='disabled')
        self.apply_btn.config(state='disabled')
        self.working = True
        self.start_btn.config(state='disabled')
        source, goal, filenames, provider = self.project.get(), self.goal.get(), self._filenames(), self.provider.get()
        self.status.config(text='AI çalışıyor. Bu pencereyi kapatma; tek çağrı tamamlanınca inceleme hazırlanacak.')

        def work():
            try:
                result = project_delivery.deliver(source, goal, filenames, provider=provider,
                    owner_confirms=True, allow_native_cli=True,
                    on_update=lambda msg: self.events.put(('log', msg)))
                self.events.put(('done', result))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, item = self.events.get_nowait()
                if kind == 'log': self._append(item)
                elif kind == 'error':
                    self.working = False
                    self.start_btn.config(state='normal')
                    self.status.config(text='Görev durdu; gerçek projeye hiçbir öneri uygulanmadı.')
                    self._append('HATA: ' + item)
                elif kind == 'done':
                    self.working = False
                    self.start_btn.config(state='normal')
                    self.review = item
                    self.diff_btn.config(state='normal')
                    self.apply_btn.config(state='normal')
                    self._append(f"ÖNERİ HAZIR: {item['review_id']} | AI: {item['ai_ok']} | test: {item['test_passed']}")
                    self._append('Değişen dosyalar: ' + ', '.join(item['files']))
                    self._append('Test raporu: ' + item['test_report'])
                    self.status.config(text='İncelemeye hazır. Test geçmediyse manuel denetim yapmadan onaylama.')
        except queue.Empty:
            pass
        self.after(120, self._poll)

    def _review_home(self):
        return core.HOME / 'delivery_reviews' / 'reviews'

    def _diff(self):
        if not self.review: return
        try:
            text = change_review.diff(self.review['review_id'], home=self._review_home(), max_chars=20000)
            win = tk.Toplevel(self)
            win.title('PARDEX Kod Farkı • ' + self.review['review_id'])
            win.geometry('900x620')
            box = tk.Text(win, wrap='none', font=('Consolas', 10))
            box.pack(fill='both', expand=True)
            box.insert('1.0', 'SHA256: ' + self.review['digest'] + '\n\n' + text)
            box.config(state='disabled')
        except Exception as exc:
            messagebox.showerror('İnceleme açılamadı', str(exc))

    def _apply(self):
        if not self.review: return
        if not self.review['test_passed']:
            if not messagebox.askyesno('Test geçmedi!',
                'Motor testi doğrulanmadı. Oyun bu hâliyle çalışmayabilir. Yine de kodu uygulamak istiyor musun?'):
                return
        digest = self.review['digest']
        if not messagebox.askyesno('Son onay',
            'Gerçek proje dosyaları değiştirilecek. İncelemeyi ve SHA256 kimliğini kontrol ettin mi?\n' + digest):
            return
        try:
            change_review.apply(self.review['review_id'], digest,
                                owner_confirms=True, home=self._review_home())
            self._append('ONAYLANDI: Değişiklik gerçek projeye uygulandı. İstersen 07_AI_DEGISIKLIK_INCELE aracından geri alabilirsin.')
            self.apply_btn.config(state='disabled')
            self.status.config(text='Uygulama tamamlandı. Oyun içinde manuel olarak test et.')
        except Exception as exc:
            messagebox.showerror('Uygulama reddedildi', str(exc))


if __name__ == '__main__':
    DeliveryConsole().mainloop()
