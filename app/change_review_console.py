"""Turkish offline change review window; never starts an AI or runs code."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import change_review


class ReviewConsole(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('PARDEX | AI Değişiklik İnceleme Merkezi')
        self.geometry('980x740')
        self.minsize(760, 550)
        self.review = None
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='AI Değişiklik İnceleme Merkezi',
                  font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Öneriler önce özel inceleme paketine alınır. Onay verene kadar gerçek proje değişmez.',
                  wraplength=900).pack(anchor='w', pady=(3, 12))
        self.project = tk.StringVar()
        self.proposal = tk.StringVar()
        self.file_names = tk.StringVar(value='scripts/player.gd')
        self.review_id = tk.StringVar()
        for caption, variable in [('Gerçek proje klasörü', self.project),
                                  ('AI öneri klasörü (ayrı olmalı)', self.proposal)]:
            row = ttk.Frame(frame)
            row.pack(fill='x', pady=3)
            ttk.Label(row, text=caption, width=32).pack(side='left')
            ttk.Entry(row, textvariable=variable).pack(side='left', expand=True, fill='x', padx=5)
            ttk.Button(row, text='Seç', command=lambda v=variable: self.pick(v)).pack(side='left')
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text='Değişen dosyalar (virgülle ayır)', width=32).pack(side='left')
        ttk.Entry(row, textvariable=self.file_names).pack(side='left', expand=True, fill='x')
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(8, 3))
        ttk.Label(row, text='Mevcut inceleme kimliği', width=32).pack(side='left')
        ttk.Entry(row, textvariable=self.review_id).pack(side='left', expand=True, fill='x')
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', pady=9)
        ttk.Button(toolbar, text='Öneriyi incelemeye al', command=self.stage).pack(side='left', padx=2)
        ttk.Button(toolbar, text='Farkları göster', command=self.show_diff).pack(side='left', padx=2)
        ttk.Button(toolbar, text='ONAYLA ve uygula', command=self.apply).pack(side='left', padx=2)
        ttk.Button(toolbar, text='Geri al', command=self.rollback).pack(side='left', padx=2)
        self.status = tk.StringVar(value='Hazır · AI çağrısı yapılmaz · Ücretli işlem yok')
        ttk.Label(frame, textvariable=self.status, wraplength=900).pack(anchor='w', pady=4)
        self.output = scrolledtext.ScrolledText(frame, wrap='none', font=('Consolas', 10))
        self.output.pack(fill='both', expand=True)
        self.output.insert('1.0', 'Değişiklikleri görmek için iki klasör ve dosya isimlerini belirle.\n'
                                    'Önemli: Bu araç AI tarafından yazılmış kodu çalıştırmaz veya otomatik yayınlamaz.\n')

    def pick(self, var):
        selected = filedialog.askdirectory(title='Klasör seç')
        if selected:
            var.set(selected)

    def _render(self, message):
        self.output.delete('1.0', 'end')
        self.output.insert('1.0', message)

    def _selected(self):
        rid = self.review_id.get().strip()
        result = change_review.summary(rid)
        self.status.set('Durum: ' + result['state'] + ' · SHA256: ' + result['digest'])
        return result

    def _handle(self, callback):
        try:
            callback()
        except (OSError, ValueError, PermissionError, RuntimeError) as err:
            messagebox.showerror('İşlem durduruldu', f'{type(err).__name__}: {err}', parent=self)

    def stage(self):
        def go():
            files = [s.strip() for s in self.file_names.get().split(',') if s.strip()]
            item = change_review.stage(self.project.get(), self.proposal.get(), files)
            self.review_id.set(item['review_id'])
            self.show_diff()
            self.status.set('İnceleme hazır: ' + item['review_id'] + ' · SHA256: ' + item['digest'])
        self._handle(go)

    def show_diff(self):
        def go():
            item = self._selected()
            shown = change_review.diff(item['review_id'], max_chars=19000)
            self._render('İnceleme: '+item['review_id']+'\n'
                'DURUM: '+item['state']+'\nSHA256: '+item['digest']+'\n\n'
                'DIFF (en fazla 19.000 karakter)\n\n'+shown+
                '\n\nUYARI: Görünen fark kısaltılmış olabilir; büyük değişiklikler için kaynak dosyaları ayrıca incele.\n')
        self._handle(go)

    def apply(self):
        def go():
            item = self._selected()
            if item['state'] != 'staged':
                raise ValueError('Yalnızca inceleme bekleyen değişiklik uygulanabilir')
            digest = item['digest']
            count = len(item['changes'])
            answer = messagebox.askyesno('PARDEX — SAHİP ONAYI',
                f'{count} dosya gerçek projede değiştirilecek.\n\n'
                f'Proje: {item["project"]}\nSHA256: {digest}\n\n'
                'Farkları gördüğünü ve bu değişikliği uygulamak istediğini onaylıyor musun?',
                icon='warning', parent=self)
            if not answer:
                return
            result = change_review.apply(item['review_id'], digest, owner_confirms=True)
            self.status.set('Uygulandı; yeniden test etmen gerekir. ' + result['review_id'])
            self._render('Değişiklik uygulandı. Kod güvenliği veya test başarısı garanti edilmez.\n'
                         'İşlem: '+result['review_id']+'\n')
        self._handle(go)

    def rollback(self):
        def go():
            item = self._selected()
            if not messagebox.askyesno('Geri alma onayı',
                'Bu incelemenin uyguladığı değişiklikleri geri almak istiyor musun?\n'
                'Sonradan senin yaptığın değişiklikler varsa işlem durdurulacaktır.',
                icon='warning', parent=self):
                return
            result = change_review.rollback(item['review_id'], item['digest'], owner_confirms=True)
            self.status.set('Geri alındı: ' + result['review_id'])
            self._render('Dosyalar önceki içeriklerine geri döndürüldü.\n')
        self._handle(go)


def main():
    ReviewConsole().mainloop()


if __name__ == '__main__':
    main()
