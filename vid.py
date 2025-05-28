import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import cv2
import threading
import os
import concurrent.futures
import pygame
import time
import tempfile

# Remove the first import of moviepy and keep only the try-except block
try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("Warning: moviepy not available. Audio preview will be disabled.")

class VideoPlayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Player")
        self.root.state('zoomed')
        
        # Configurações iniciais
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Inicializa pygame para áudio
        pygame.init()
        pygame.mixer.init()
        
        self.video_path = None
        self.cap = None
        self.playing = False
        self.cap_lock = threading.Lock()
        self.playing_lock = threading.Lock()
        self.progress_var = tk.DoubleVar()
        
        # Variáveis para controle de preview
        self.preview_playing = False
        self.preview_thread = None
        self.temp_audio_file = None
        
        self.create_widgets()

    def create_widgets(self):
        # Criando frame principal que se adaptará ao redimensionamento
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Frame dos botões no topo
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 5))  # Added pady to separate from preview

        # Botões existentes...
        self.select_btn = tk.Button(button_frame, text="Selecionar Video", command=self.select_video)
        self.select_btn.grid(row=0, column=0, padx=5)

        self.play_btn = tk.Button(button_frame, text="Play", command=self.play_video)
        self.play_btn.grid(row=0, column=1, padx=5)
        self.play_btn['state'] = 'disabled'  # Inicia desativado

        self.pause_btn = tk.Button(button_frame, text="Pause", command=self.pause_video)
        self.pause_btn.grid(row=0, column=2, padx=5)
        self.pause_btn['state'] = 'disabled'  # Inicia desativado

        self.resume_btn = tk.Button(button_frame, text="Continuar", command=self.resume_video)
        self.resume_btn.grid(row=0, column=3, padx=5)
        self.resume_btn['state'] = 'disabled'  # Inicia desativado

        self.stop_btn = tk.Button(button_frame, text="Stop", command=self.stop_video)
        self.stop_btn.grid(row=0, column=4, padx=5)
        self.stop_btn['state'] = 'disabled'

        self.edit_btn = tk.Button(button_frame, text="EDITAR VIDEO", command=self.edit_video)
        self.edit_btn.grid(row=0, column=5, padx=5)
        self.edit_btn['state'] = 'disabled'

        self.extract_btn = tk.Button(button_frame, text="EXTRAIR TODOS OS FRAMES", command=self.extract_frames)
        self.extract_btn.grid(row=0, column=6, padx=5)
        self.extract_btn['state'] = 'disabled'

        self.quit_btn = tk.Button(button_frame, text="SAIR", command=self.quit_app)
        self.quit_btn.grid(row=0, column=7, padx=5)

        # Frame central para preview com altura fixa
        preview_container = tk.Frame(main_frame, height=600)  # Fixed height
        preview_container.pack(fill='x', pady=5)
        preview_container.pack_propagate(False)  # Prevents the frame from shrinking

        # Preview label dentro do container
        self.preview_label = tk.Label(preview_container)
        self.preview_label.pack(expand=True, fill='both')

        # Frame inferior para controles de extração
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(fill='x', pady=(5, 0), side='bottom')

        # Frame para progresso
        self.progress_frame = tk.Frame(bottom_frame)
        self.progress_frame.pack(fill='x', pady=5)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill='x')
        
        self.progress_label = tk.Label(self.progress_frame, text="")
        self.progress_label.pack()

    def _extract_audio(self):
        """Extrai áudio do vídeo para arquivo temporário"""
        if not MOVIEPY_AVAILABLE:
            print("Audio extraction not available - moviepy module not found")
            return None
            
        try:
            if self.temp_audio_file:
                pygame.mixer.music.unload()
                os.remove(self.temp_audio_file)
                
            video = VideoFileClip(self.video_path)
            if video.audio is not None:
                temp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                self.temp_audio_file = temp.name
                video.audio.write_audiofile(self.temp_audio_file, verbose=False, logger=None)
                video.close()
                return self.temp_audio_file
        except Exception as e:
            print(f"Erro ao extrair áudio: {e}")
        return None

    def _update_button_states(self, state='normal'):
        """Atualiza o estado de todos os botões que dependem da seleção do vídeo"""
        self.play_btn['state'] = state
        self.pause_btn['state'] = state
        self.resume_btn['state'] = state
        self.stop_btn['state'] = state
        self.edit_btn['state'] = state
        self.extract_btn['state'] = state
    
    def select_video(self):
        self.video_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4;*.avi;*.mov;*.mkv;*.wmv;*.gif")])
        if self.video_path:
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                messagebox.showerror("Erro", "Não foi possível abrir o vídeo selecionado!")
                self._update_button_states('disabled')  # Desativa botões se falhar
                return
            self._update_button_states('normal')  # Ativa botões se sucesso
            self.show_preview()
        else:
            self._update_button_states('disabled')  # Desativa botões se nenhum arquivo selecionado

    def show_preview(self):
        if not self.cap or not self.cap.isOpened():
            messagebox.showwarning("Aviso", "Nenhum vídeo carregado para preview!")
            return
        
        # Para preview anterior se existir
        self.stop_preview()
        
        # Extrai áudio
        audio_path = self._extract_audio()
        
        # Obtém FPS do vídeo
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        delay = 1.0 / fps if fps > 0 else 0.033  # 30 FPS default
        
        def update_preview():
            self.preview_playing = True
            self.play_btn['state'] = 'disabled'  # Disable play button while playing
            
            # Inicia áudio se disponível
            if audio_path:
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
            
            while self.preview_playing:
                ret, frame = self.cap.read()
                if not ret:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    if audio_path:
                        pygame.mixer.music.play()
                    continue
                
                # Processa frame
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Calcula dimensões
                window_width = self.preview_label.winfo_width()
                window_height = self.preview_label.winfo_height()
                
                if window_width > 1 and window_height > 1:
                    aspect_ratio = frame.shape[1] / frame.shape[0]
                    if window_width / window_height > aspect_ratio:
                        preview_height = int(window_height * 1.5)  # Scale height by 1.5
                        preview_width = int(preview_height * aspect_ratio)
                    else:
                        preview_width = int(window_width * 1.5)  # Scale width by 1.5
                        preview_height = int(preview_width / aspect_ratio)
                    
                    frame = cv2.resize(frame, (preview_width, preview_height))
                
                # Atualiza preview
                image = Image.fromarray(frame)
                photo = ImageTk.PhotoImage(image)
                self.preview_label.config(image=photo)
                self.preview_label.image = photo
                
                # Controle de tempo
                self.root.update()
                time.sleep(delay)
        
        # Inicia preview em thread separada
        self.preview_thread = threading.Thread(target=update_preview)
        self.preview_thread.daemon = True
        self.preview_thread.start()

    def stop_preview(self):
        """Para a reprodução do preview"""
        self.preview_playing = False
        self.play_btn['state'] = 'normal'  # Re-enable play button when stopped
        if self.preview_thread and self.preview_thread.is_alive():
            self.preview_thread.join()
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

    def _validate_video_file(self):
        if not self.video_path or not os.path.exists(self.video_path):
            messagebox.showerror("Erro", "Arquivo de vídeo não encontrado!")
            return False
        return True
    
    def play_video(self):
        if not self._validate_video_file():
            return
        self.show_preview()  # Reuse existing preview functionality

    def pause_video(self):
        self.preview_playing = False
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()

    def resume_video(self):
        self.preview_playing = True
        if not self.preview_thread or not self.preview_thread.is_alive():
            self.show_preview()
        else:
            pygame.mixer.music.unpause()
            
    def stop_video(self):
        self.stop_preview()
        with self.playing_lock:
            self.playing = False
        with self.cap_lock:
            if self.cap:
                self.cap.release()
        cv2.destroyAllWindows()

    def edit_video(self):
        messagebox.showinfo("Informação", "Funcionalidade de edição será implementada em breve!")

    def quit_app(self):
        self.stop_preview()
        self.stop_video()
        if self.temp_audio_file and os.path.exists(self.temp_audio_file):
            try:
                os.remove(self.temp_audio_file)
            except:
                pass
        pygame.quit()
        self.root.quit()
        self.root.destroy()

    def save_frame(self, frame, frame_path):
        """Salva um frame individual como arquivo TIFF"""
        cv2.imwrite(frame_path, frame, [cv2.IMWRITE_TIFF_COMPRESSION, cv2.IMWRITE_TIFF_COMPRESSION_DEFLATE])

    # Altere o comando do botão de extração:
    def extract_frames(self):
        # self.export_dialog()  # Removido, pois não existe
        if not self._validate_video_file():
            return

        # Let user select output directory
        output_dir = filedialog.askdirectory(title="Selecione a pasta para salvar os frames")
        if not output_dir:  # User cancelled
            return

        if self.cap is not None:
            self.cap.release()
            self.cap = None

        BATCH_SIZE = 50
        cap = None
        
        try:
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                messagebox.showerror("Erro", "Erro ao abrir o vídeo!")
                return

            video_name = os.path.splitext(os.path.basename(self.video_path))[0].replace(' ', '_')
            video_name = video_name.replace("'", "")
            video_name = video_name.replace(":", "")
            video_name = video_name.replace(";", "")
            video_name = video_name.replace("-", "")
            video_name = video_name.replace("–", "")
            video_name = video_name.replace("—", "")
            video_name = video_name.replace(".", "")
        
            output_dir = os.path.join(output_dir, video_name)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            frame_count = 0
            batch_frames = []

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_path = os.path.join(output_dir, f"{video_name}_{frame_count:04d}.tiff")
                batch_frames.append((frame.copy(), frame_path))
                frame_count += 1

                # Processa o lote quando atingir o tamanho definido
                if len(batch_frames) >= BATCH_SIZE:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                        futures = [
                            executor.submit(self.save_frame, frame, path)
                            for frame, path in batch_frames
                        ]
                        concurrent.futures.wait(futures)
                    batch_frames.clear()

            # Processa o último lote se houver frames restantes
            if batch_frames:
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [
                        executor.submit(self.save_frame, frame, path)
                        for frame, path in batch_frames
                    ]
                    concurrent.futures.wait(futures)

            # Ask user if they want to copy the video file
            if messagebox.askyesno("Copiar Arquivo de Vídeo", 
                                 "Deseja copiar o arquivo de vídeo original para a pasta de destino?"):
                video_filename = os.path.basename(self.video_path)
                video_destination = os.path.join(output_dir, video_filename)
                # Copia o arquivo de vídeo
                if os.path.exists(video_destination):
                    os.remove(video_destination)
                    # Renomeia o arquivo de vídeo
                    video_destination = os.path.join(output_dir, f"{video_name}.mp4")
                    if os.path.exists(video_destination):
                        os.remove(video_destination
                        )

                
                # os.rename(self.video_path, video_destination)

            messagebox.showinfo("Sucesso", f"Extração concluída!\nFrames salvos em:\n{output_dir}")

        except PermissionError:
            messagebox.showerror("Erro", "Não foi possível mover o arquivo de vídeo. Ele pode estar em uso.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro durante a extração: {str(e)}")
        finally:
            if cap is not None:
                cap.release()
                cv2.destroyAllWindows()

        

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoPlayerApp(root)
    root.mainloop()
