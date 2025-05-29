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
import shutil
import numpy as np

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

        self.preview_cap = None  # VideoCapture dedicado para o preview
        self.preview_lock = threading.Lock()  # Lock específico para o preview
        
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
            # --- NEW CODE BELOW ---
            import os
            # Path, name, extension
            video_full_path = self.video_path
            # File size in MB
            file_size = os.path.getsize(self.video_path) / (1024 * 1024)
            # Frame count
            frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            # Dimensions
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            # Duration in seconds
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            duration = frame_count / fps if fps > 0 else 0
            # Format duration as mm:ss
            mins = int(duration // 60)
            secs = int(duration % 60)
            duration_str = f"{mins:02d}:{secs:02d}"
            # Set window title
            self.root.title(f"Video Player | {video_full_path} | {file_size:.2f} MB | {width}x{height} | {duration_str} | {frame_count} frames")
            
            # Initialize total_frames for playback progress
            self.total_preview_frames = int(self.preview_cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self.preview_cap else 0
            self.show_preview()
        else:
            self._update_button_states('disabled')  # Desativa botões se nenhum arquivo selecionado
    
    def show_preview(self):
        if not self.video_path:
            return

        # Para preview anterior se existir
        self.stop_preview()

        # Cria um VideoCapture dedicado para o preview
        with self.preview_lock:
            self.preview_cap = cv2.VideoCapture(self.video_path)
            if not self.preview_cap.isOpened():
                messagebox.showwarning("Aviso", "Não foi possível abrir o vídeo para preview!")
                self.preview_cap = None
                return
            # Set total_preview_frames here as well, in case select_video didn't set it
            self.total_preview_frames = int(self.preview_cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Extrai áudio
        audio_path = self._extract_audio()
        
        # Obtém FPS do vídeo
        fps = self.preview_cap.get(cv2.CAP_PROP_FPS)
        delay = 1.0 / fps if fps > 0 else 0.033  # 30 FPS default
        
        def update_preview():
            try:
                with self.preview_lock:
                    if self.preview_cap is None or not self.preview_playing:
                        # Stop audio if it's playing and preview is stopping
                        if pygame.mixer.music.get_busy():
                            pygame.mixer.music.stop()
                        # Reset progress bar when preview stops
                        self.root.after(0, lambda: self._update_playback_progress(0, self.total_preview_frames))
                        return # Stop scheduling if preview is not playing or cap is released

                    ret, frame = self.preview_cap.read()
                    current_frame_pos = int(self.preview_cap.get(cv2.CAP_PROP_POS_FRAMES))
                    
                if not ret:
                    # Loop video and audio if end is reached
                    with self.preview_lock:
                        if self.preview_cap is not None:
                            self.preview_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            if audio_path:
                                pygame.mixer.music.play()
                    # Schedule the next frame after looping
                    self.root.after(int(delay * 1000), update_preview)
                    return
                    
                # Processa frame mantendo aspect ratio corretamente
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img_height, img_width = frame.shape[:2]
                aspect_ratio = img_width / img_height
                
                # Obtém dimensões disponíveis
                window_width = self.preview_label.winfo_width()
                window_height = self.preview_label.winfo_height()
                
                if window_width > 1 and window_height > 1:
                    # Calcula novas dimensões que cabem na janela mantendo a proporção
                    if window_width / window_height > aspect_ratio:
                        # Limita pela altura
                        new_height = window_height
                        new_width = int(new_height * aspect_ratio)
                    else:
                        # Limita pela largura
                        new_width = window_width
                        new_height = int(new_width / aspect_ratio)
                    
                    # Redimensiona mantendo a proporção original
                    frame = cv2.resize(frame, (new_width, new_height))
                    
                    # Cria uma imagem preta do tamanho da janela
                    bg = np.zeros((window_height, window_width, 3), dtype=np.uint8)
                    
                    # Centraliza a imagem redimensionada
                    x_offset = (window_width - new_width) // 2
                    y_offset = (window_height - new_height) // 2
                    bg[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = frame
                    frame = bg
                
                # Atualiza preview
                image = Image.fromarray(frame)
                photo = ImageTk.PhotoImage(image)
                self.preview_label.config(image=photo)
                self.preview_label.image = photo
                
                # Update playback progress bar
                self.root.after(0, lambda: self._update_playback_progress(current_frame_pos, self.total_preview_frames))

                # Schedule the next frame update
                self.root.after(int(delay * 1000), update_preview)
            except Exception as e:
                print(f"Erro no preview: {e}")
                self.preview_playing = False # Ensure preview stops on error
                # Stop audio on error
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                # Reset progress bar on error
                self.root.after(0, lambda: self._update_playback_progress(0, self.total_preview_frames))
            finally:
                pass
        
        # Inicia preview em thread separada (this thread will only start the first frame update)
        # The subsequent updates are scheduled by self.root.after
        def start_preview_thread():
            try:
                self.preview_playing = True
                self.play_btn['state'] = 'disabled'
                
                # Inicia áudio se disponível
                if audio_path:
                    pygame.mixer.music.load(audio_path)
                    pygame.mixer.music.play()
                
                # Schedule the first frame update
                self.root.after(0, update_preview)
                
            except Exception as e:
                print(f"Erro ao iniciar thread de preview: {e}")
                self.preview_playing = False
                self.play_btn['state'] = 'normal'
                # Stop audio on error
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()

        self.preview_thread = threading.Thread(target=start_preview_thread)
        self.preview_thread.daemon = True
        self.preview_thread.start()

    def stop_preview(self):
        """Para a reprodução do preview"""
        self.preview_playing = False
        
        # Para o áudio
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        
        # Libera o VideoCapture do preview
        with self.preview_lock:
            if self.preview_cap is not None:
                self.preview_cap.release()
                self.preview_cap = None
        
        # Update button state when preview stops
        self.play_btn['state'] = 'normal'

        # Reset progress bar when preview stops
        self.root.after(0, lambda: self._update_playback_progress(0, self.total_preview_frames))

        # No need to join the thread here as it only schedules the first call
        # The scheduled calls will stop when preview_playing is False

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
                self.cap = None
        cv2.destroyAllWindows()

    def edit_video(self):
        messagebox.showinfo("Informação", "Funcionalidade de edição será implementada em breve!")

    def quit_app(self):
        self.stop_preview()
        self.stop_video()
        if self.temp_audio_file and os.path.exists(self.temp_audio_file):
            pygame.mixer.music.unload()  # Garantir que o arquivo de áudio seja liberado
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

    def extract_frames(self):
        if not self._validate_video_file():
            return
        output_dir = filedialog.askdirectory(title="Selecione a pasta para salvar os frames")
        if not output_dir:
            return
        threading.Thread(target=self._extract_frames_worker, args=(output_dir,)).start()

    def _extract_frames_worker(self, output_dir):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        BATCH_SIZE = 50
        cap = None
        try:
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                self.root.after(0, lambda: messagebox.showerror("Erro", "Erro ao abrir o vídeo!"))
                return
            video_name = os.path.splitext(os.path.basename(self.video_path))[0].replace(' ', '_')
            video_name = video_name.replace("'", "").replace(":", "").replace(";", "").replace("-", "").replace("–", "").replace("—", "").replace(".", "")
            output_dir = os.path.join(output_dir, video_name)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            frame_count = 0
            batch_frames = []
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                frame_path = os.path.join(output_dir, f"{video_name}_{frame_count:04d}.tiff")
                batch_frames.append((frame.copy(), frame_path))
                frame_count += 1
                if len(batch_frames) >= BATCH_SIZE:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                        futures = [executor.submit(self.save_frame, frame, path) for frame, path in batch_frames]
                        concurrent.futures.wait(futures)
                    batch_frames.clear()
                # Atualiza barra de progresso
                self.root.after(0, lambda fc=frame_count, tf=total_frames: self._update_progress(fc, tf))
            if batch_frames:
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [executor.submit(self.save_frame, frame, path) for frame, path in batch_frames]
                    concurrent.futures.wait(futures)
            # Copia o vídeo se desejado
            def copy_video():
                if messagebox.askyesno("Copiar Arquivo de Vídeo", 
                                     "Deseja copiar o arquivo de vídeo original para a pasta de destino?"):
                    video_filename = os.path.basename(self.video_path)
                    video_destination = os.path.join(output_dir, video_filename)
                    if os.path.exists(video_destination):
                        os.remove(video_destination)
                        video_destination = os.path.join(output_dir, f"{video_name}.mp4")
                        if os.path.exists(video_destination):
                            os.remove(video_destination)
                    shutil.copy2(self.video_path, video_destination)
                messagebox.showinfo("Sucesso", f"Extração concluída!\nFrames salvos em:\n{output_dir}")
                self._update_progress(total_frames, total_frames)
            self.root.after(0, copy_video)  # Adicionado after para evitar problemas de UI
        except PermissionError:
            messagebox.showerror("Erro", "Não foi possível mover o arquivo de vídeo. Ele pode estar em uso.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro durante a extração: {str(e)}")
        finally:
            if cap is not None:
                cap.release()
            cv2.destroyAllWindows()
            # ADICIONE ISSO APÓS O finally:
            self.cap = cv2.VideoCapture(self.video_path)

    def _update_playback_progress(self, current_frame, total_frames):
        """Update the progress bar and label with current playback position"""
        if total_frames > 0:
            progress = (current_frame / total_frames) * 100
            self.progress_var.set(progress)
            self.progress_label.config(text=f"Frame: {current_frame}/{total_frames} ({progress:.1f}%)")
        self.root.update_idletasks()

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoPlayerApp(root)
    root.mainloop()
