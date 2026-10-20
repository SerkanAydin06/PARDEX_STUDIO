"""Small Turkish Tkinter controller for approved worker sessions."""
import tkinter as tk
from tkinter import messagebox
import threading
import queue
import worker_supervisor as worker

class Window(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PARDEX | AI Çalışan Konsolu")
        self.geometry("800x480")
        self.ids=()
        self.running=False
        self.messages=queue.Queue()
        tk.Label(self,text="AI Çalışan Konsolu",font=("Segoe UI",18)).pack(pady=12)
        tools=tk.Frame(self)
        tools.pack(pady=5)
        self.refresh_button=tk.Button(tools,text="Ücretsiz önizleme",command=self.preview)
        self.refresh_button.pack(side="left",padx=5)
        self.run_button=tk.Button(tools,text="Onayla ve vardiyayı başlat",command=self.start)
        self.run_button.pack(side="left",padx=5)
        tk.Button(tools,text="Sonraki görevden önce dur",command=self.stop).pack(side="left",padx=5)
        tk.Label(self,text="Durdurma, çalışan AI komutunu anında kesmez. Sonuçlar ayrıca onay bekler.").pack()
        self.text=tk.Text(self,wrap="word",state="disabled")
        self.text.pack(fill="both",expand=True,padx=14,pady=12)
        self.after(150,self.poll)
        self.protocol("WM_DELETE_WINDOW",self.close)
        self.preview()

    def show(self,s):
        self.text.config(state="normal")
        self.text.insert("end",str(s)+"\n")
        self.text.see("end")
        self.text.config(state="disabled")

    def preview(self):
        if self.running:return
        self.ids=()
        try:
            p=worker.preview(max_tasks=2,max_minutes=30)
            self.show("Yeni plan (AI çağrısı yok):")
            for task in p["tasks"]:
                self.show("%s | %s | %s" %(task["id"],task["project"],task["provider"]))
            if p.get("blocked_reason"):self.show("Engel: "+p["blocked_reason"])
            else:self.ids=tuple(t["id"] for t in p["tasks"])
            if not self.ids:self.show("Onaylı uygun görev yok.")
        except Exception as exc:
            self.show("Hata: "+type(exc).__name__)

    def start(self):
        if self.running or not self.ids:return
        if not messagebox.askyesno("Sahip onayı",
            "Şu önceden onaylı görevler çalışsın mı?\n"+"\n".join(self.ids)+
            "\nAI kullanım kotası tüketilebilir."):return
        ids=self.ids
        self.ids=()
        self.running=True
        self.run_button.config(state="disabled")
        self.refresh_button.config(state="disabled")
        def work():
            try:self.messages.put(("done",worker.run(ids,owner_confirms=True)))
            except Exception as exc:self.messages.put(("error",type(exc).__name__))
        threading.Thread(target=work,daemon=True).start()

    def stop(self):
        active=next((s for s in worker.recent() if s["state"]=="running"),None)
        if not active:self.show("Aktif vardiya yok.");return
        if messagebox.askyesno("Durdurma","Bir sonraki görevden önce durulsun mu?"):
            worker.request_stop(active["id"],owner_confirms=True)
            self.show("Durdurma talebi kaydedildi.")

    def poll(self):
        try:
            while True:
                kind,data=self.messages.get_nowait()
                if kind=="error":self.show("Vardiya hatası: "+data)
                else:
                    self.show("Vardiya: "+data["state"]+" | "+data.get("reason",""))
                    for x in data["processed"]:self.show(x["task_id"]+" => "+x["status"])
                self.running=False
                self.run_button.config(state="normal")
                self.refresh_button.config(state="normal")
        except queue.Empty:pass
        self.after(150,self.poll)

    def close(self):
        if self.running:
            messagebox.showwarning("Çalışma sürüyor","Aktif görevin bitmesini bekleyin; durdurma isteği yalnızca görevler arasında işler.")
        else:self.destroy()

if __name__=="__main__":
    Window().mainloop()
