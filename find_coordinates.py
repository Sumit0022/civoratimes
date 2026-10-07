import tkinter as tk
from PIL import Image, ImageTk
import sys

class CoordinateFinder:
    def __init__(self, master, image_path):
        self.master = master
        self.master.title(f"Find Coordinates - {image_path}")
        
        try:
            self.img = Image.open(image_path)
        except Exception as e:
            print(f"Error loading image: {e}")
            sys.exit(1)
            
        # Scale down if image is too large to fit on screen
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
        
        print(f"Loaded {image_path}")
        print("INSTRUCTIONS: Click and drag a box on the image where you want the text to go.")
        
    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)
        
    def on_drag(self, event):
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
        
    def on_release(self, event):
        end_x, end_y = event.x, event.y
        
        # Calculate original coordinates based on scale factor
        x1 = int(min(self.start_x, end_x) / self.scale_factor)
        x2 = int(max(self.start_x, end_x) / self.scale_factor)
        y1 = int(min(self.start_y, end_y) / self.scale_factor)
        y2 = int(max(self.start_y, end_y) / self.scale_factor)
        
        print("-" * 40)
        print("Use these values in your config:")
        print(f"Bounding Box: [{x1}, {y1}, {x2}, {y2}]")
        print(f"Max Width allowed: {x2-x1}px")
        print(f"Max Height allowed: {y2-y1}px")
        print("-" * 40)

if __name__ == "__main__":
    import sys
    # Default to BJP template, but can pass others
    image_path = r"C:\Users\DELL\Desktop\format\BJP.png"
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        
    root = tk.Tk()
    app = CoordinateFinder(root, image_path)
    root.mainloop()
