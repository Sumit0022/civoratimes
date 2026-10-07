import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

class CoordinateFinder:
    def __init__(self, master, image_path):
        self.master = master
        self.master.title(f"Draw a box for your text!")
        
        self.img = Image.open(image_path)
        screen_height = master.winfo_screenheight()
        self.scale_factor = 1.0
        
        if self.img.height > screen_height - 100:
            self.scale_factor = (screen_height - 100) / self.img.height
            new_width = int(self.img.width * self.scale_factor)
            new_height = int(self.img.height * self.scale_factor)
            display_img = self.img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            display_img = self.img

        self.tk_img = ImageTk.PhotoImage(display_img)
        self.canvas = tk.Canvas(master, width=display_img.width, height=display_img.height)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='blue', width=4)
        
    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)
        
    def on_release(self, event):
        x1 = int(min(self.start_x, event.x) / self.scale_factor)
        x2 = int(max(self.start_x, event.x) / self.scale_factor)
        y1 = int(min(self.start_y, event.y) / self.scale_factor)
        y2 = int(max(self.start_y, event.y) / self.scale_factor)
        
        coords = f"[{x1}, {y1}, {x2}, {y2}]"
        
        self.master.clipboard_clear()
        self.master.clipboard_append(coords)
        
        messagebox.showinfo("Coordinates Copied!", f"Box ban gaya!\n\nCoordinates: {coords}\n\nYe coordinates automatically COPY ho gaye hain. Ab aap ise chat mein PASTE kar sakte hain.")

if __name__ == "__main__":
    import sys
    image_path = r"C:\Users\DELL\Desktop\format\BJP.png"
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    root = tk.Tk()
    root.attributes('-topmost', True) # Bring to front
    app = CoordinateFinder(root, image_path)
    root.mainloop()
