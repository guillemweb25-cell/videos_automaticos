export interface Video {
  id: number;
  title: string;
  status: string;
}

export interface VideoResponse extends Video {
  created_at: string;
  last_error?: string;
  is_uploaded?: boolean;
  youtube_video_id?: string;
  youtube_title?: string;
  youtube_description?: string;
  youtube_tags?: string;
  width?: number;
  height?: number;
  voice?: string;
  style?: string;
  max_images_per_paragraph?: number;
}

export interface ParagraphPrompt {
  paragraph_id: number;
  seconds: number;
  prompts: {
    id: number;
    prompt: string;
    url: string;
    cost?: {
      amount: number;
      currency?: string;
    };
  }[];
}

export interface UserResponse {
  id: number;
  email: string;
  is_active: boolean;
}

export interface ChannelResponse {
  id: number;
  name: string;
  handle?: string;
  creds_dir?: string;
}

export interface YouTubeChannelInfo {
  id: string;
  snippet: {
    title: string;
    description: string;
    thumbnails: {
      default: { url: string };
    };
  };
  statistics: {
    viewCount: string;
    subscriberCount: string;
    videoCount: string;
  };
}

export interface YouTubeVideo {
  id: string;
  title: string;
  thumbnail: string;
  published_at: string;
  view_count?: string;
}

export const API_URL = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8500`;

class ApiClient {
  private baseUrl = API_URL;

  private getHeaders(auth = false) {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (auth) {
      const token = localStorage.getItem('token');
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }
    return headers;
  }

  // Auth Methods
  async login(email: string, password: string): Promise<{ access_token: string }> {
    const res = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Error al iniciar sesión');
    }
    const data = await res.json();
    localStorage.setItem('token', data.access_token);
    return data;
  }

  async register(email: string, password: string): Promise<UserResponse> {
    const res = await fetch(`${this.baseUrl}/auth/register`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Error al registrarse');
    }
    return res.json();
  }

  async getMe(): Promise<UserResponse> {
    const res = await fetch(`${this.baseUrl}/auth/me`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) {
      if (res.status === 401) {
        localStorage.removeItem('token');
        throw new Error('TOKEN_EXPIRED');
      }
      throw new Error('NETWORK_ERROR');
    }
    return res.json();
  }

  logout() {
    localStorage.removeItem('token');
  }

  // Channel Methods
  async getChannels(): Promise<ChannelResponse[]> {
    const res = await fetch(`${this.baseUrl}/channels/`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener canales');
    return res.json();
  }

  async createChannel(name: string, handle?: string): Promise<ChannelResponse> {
    const res = await fetch(`${this.baseUrl}/channels/`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify({ name, handle }),
    });
    if (!res.ok) throw new Error('Error al crear canal');
    return res.json();
  }

  async updateChannel(channelId: number, data: Partial<ChannelResponse>): Promise<ChannelResponse> {
    const res = await fetch(`${this.baseUrl}/channels/${channelId}`, {
      method: 'PATCH',
      headers: this.getHeaders(true),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Error al actualizar canal');
    return res.json();
  }

  async deleteChannel(channelId: number): Promise<void> {
    const res = await fetch(`${this.baseUrl}/channels/${channelId}`, {
      method: 'DELETE',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al eliminar canal');
  }

  // YouTube Methods
  async getYouTubeChannelInfo(channelId: number): Promise<YouTubeChannelInfo> {
    const res = await fetch(`${this.baseUrl}/youtube/channel/${channelId}`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener info de YouTube');
    return res.json();
  }

  async getYouTubeVideos(channelId: number): Promise<YouTubeVideo[]> {
    const res = await fetch(`${this.baseUrl}/youtube/videos/${channelId}`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener vídeos de YouTube');
    return res.json();
  }

  async getYouTubeShorts(channelId: number): Promise<YouTubeVideo[]> {
    const res = await fetch(`${this.baseUrl}/youtube/shorts/${channelId}`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener shorts de YouTube');
    return res.json();
  }

  async downloadYouTubeAudio(channelId: number, url: string): Promise<{ ok: boolean }> {
    const res = await fetch(`${this.baseUrl}/youtube/download/${channelId}?url=${encodeURIComponent(url)}`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error en la descarga');
    return res.json();
  }

  async getDownloadedFiles(channelId: number): Promise<string[]> {
    const res = await fetch(`${this.baseUrl}/youtube/downloads/${channelId}`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener descargas');
    return res.json();
  }

  // Video Methods
  async getVideosByChannel(channelId: number): Promise<VideoResponse[]> {
    const res = await fetch(`${this.baseUrl}/videos/channel/${channelId}`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener vídeos');
    return res.json();
  }

  async createVideo(data: { channel_id: number; title: string; voice?: string; style?: string; width?: number; height?: number; max_images_per_paragraph?: number }): Promise<VideoResponse> {
    const res = await fetch(`${this.baseUrl}/videos/`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Error al crear vídeo');
    return res.json();
  }

  async deleteVideo(videoId: number): Promise<void> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}`, {
      method: 'DELETE',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al eliminar vídeo');
  }

  async uploadScript(videoId: number, script: string): Promise<{ ok: boolean; paragraphs: number }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/script`, {
      method: 'POST',
      headers: { ...this.getHeaders(true), 'Content-Type': 'application/json' },
      body: JSON.stringify({ script }),
    });
    if (!res.ok) throw new Error('Error al subir guion');
    return res.json();
  }

  async getVideoScript(videoId: number): Promise<{ script: string }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/script`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener guion');
    return res.json();
  }

  async generateAudio(videoId: number, voice: string, provider: string): Promise<{ ok: boolean; total_seconds: number }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/audio?voice=${voice}&provider=${provider}`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al generar audio');
    return res.json();
  }

  async generateImages(videoId: number, style: string, maxImages: number, modelId?: string, generationMode?: string): Promise<{ ok: boolean; count: number }> {
    let url = `${this.baseUrl}/videos/${videoId}/images?style_name=${style}&max_images_per_paragraph=${maxImages}`;
    if (modelId) url += `&model_id=${encodeURIComponent(modelId)}`;
    if (generationMode) url += `&generation_mode=${encodeURIComponent(generationMode)}`;
    
    const res = await fetch(url, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al generar imágenes');
    const data = await res.json();
    
    // If background processing, poll for completion
    if (data.background) {
      return this.pollVideoStatus(videoId);
    }
    return data;
  }

  async getVideoStatus(videoId: number): Promise<{ status: string; last_error?: string }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/status`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener estado del vídeo');
    return res.json();
  }

  private async pollVideoStatus(videoId: number, maxWaitMs = 600000): Promise<{ ok: boolean; count: number }> {
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      await new Promise(r => setTimeout(r, 5000)); // Poll every 5 seconds
      const status = await this.getVideoStatus(videoId);
      if (status.status === 'images_ready') {
        return { ok: true, count: 0 };
      }
      if (status.status === 'failed') {
        throw new Error(status.last_error || 'Image generation failed');
      }
      // Still generating, continue polling
    }
    throw new Error('Image generation timed out after 10 minutes');
  }

  async getImagesData(videoId: number): Promise<{ 
    items: ParagraphPrompt[], 
    style: string, 
    thumbnail_url?: string,
    thumbnail?: { hook: string; visual_prompt: string }
  }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/images_data`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener datos de imágenes');
    return res.json();
  }

  async renderVideo(videoId: number, subtitles: boolean = false): Promise<{ ok: boolean; output: string }> {
    let url = `${this.baseUrl}/videos/${videoId}/render`;
    if (subtitles) url += '?subtitles=true';
    const res = await fetch(url, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al renderizar vídeo');
    return res.json();
  }

  async generateSEO(videoId: number): Promise<{ ok: boolean; description: string; hashtags: string[] }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/seo`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al generar SEO');
    return res.json();
  }

  async addImage(videoId: number, paragraph_id: number, style?: string, modelId?: string, generationMode?: string): Promise<{ok: boolean, image: any}> {
    let url = `${this.baseUrl}/videos/${videoId}/add-image?paragraph_id=${paragraph_id}`;
    if (style) url += `&style_name=${encodeURIComponent(style)}`;
    if (modelId) url += `&model_id=${encodeURIComponent(modelId)}`;
    if (generationMode) url += `&generation_mode=${encodeURIComponent(generationMode)}`;
    
    const response = await fetch(url, {
      method: "POST",
      headers: this.getHeaders(true),
    });
    if (!response.ok) throw new Error("Failed to add image");
    return response.json();
  }

  async removeImage(videoId: number, paragraphId: number, imageId: number): Promise<{ok: boolean}> {
    const response = await fetch(`${this.baseUrl}/videos/${videoId}/remove-image?paragraph_id=${paragraphId}&image_id=${imageId}`, {
      method: "DELETE",
      headers: this.getHeaders(true),
    });
    if (!response.ok) throw new Error("Failed to remove image");
    return response.json();
  }

  async regenerateImage(videoId: number, paragraphId: number, imageId: number, customPrompt?: string, modelId?: string, generationMode?: string): Promise<{ ok: boolean, url: string }> {
    let url = `${this.baseUrl}/videos/${videoId}/regenerate-image?paragraph_id=${paragraphId}&image_id=${imageId}`;
    if (customPrompt) url += `&custom_prompt=${encodeURIComponent(customPrompt)}`;
    if (modelId) url += `&model_id=${encodeURIComponent(modelId)}`;
    if (generationMode) url += `&generation_mode=${encodeURIComponent(generationMode)}`;

    const res = await fetch(url, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al regenerar imagen');
    return res.json();
  }

  async regeneratePrompt(videoId: number, paragraphId: number, imageId: number): Promise<{ ok: boolean, prompt: string }> {
    const url = `${this.baseUrl}/videos/${videoId}/regenerate-prompt?paragraph_id=${paragraphId}&image_id=${imageId}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al regenerar prompt');
    return res.json();
  }

  async getConfig(): Promise<{ 
    voices: { tiktok: { id: string, name: string }[], elevenlabs: { id: string, name: string }[] },
    styles: { id: string, name: string }[],
    leonardo_models: { id: string, name: string }[],
    generation_modes: { id: string, name: string, cost: number }[]
  }> {
    const res = await fetch(`${this.baseUrl}/videos/config`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener configuración');
    return res.json();
  }

  async regenerateThumbnailHook(videoId: number): Promise<{ ok: boolean, hook: string }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/regenerate-thumbnail-hook`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al regenerar gancho');
    return res.json();
  }

  async regenerateThumbnailVisualPrompt(videoId: number): Promise<{ ok: boolean, visual_prompt: string }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/regenerate-thumbnail-visual-prompt`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al regenerar prompt visual');
    return res.json();
  }

  async uploadThumbnail(videoId: number, file: File): Promise<{ ok: boolean, url: string }> {
    const formData = new FormData();
    formData.append('file', file);
    
    const token = localStorage.getItem('token');
    const headers: HeadersInit = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`${this.baseUrl}/videos/${videoId}/upload-thumbnail`, {
      method: 'POST',
      headers: headers,
      body: formData,
    });
    if (!res.ok) throw new Error('Error al subir miniatura');
    return res.json();
  }

  async generateThumbnail(videoId: number, hook?: string, visualPrompt?: string, modelId?: string): Promise<{ ok: boolean, url: string }> {
    let url = `${this.baseUrl}/videos/${videoId}/generate-thumbnail?`;
    if (hook) url += `hook=${encodeURIComponent(hook)}&`;
    if (visualPrompt) url += `visual_prompt=${encodeURIComponent(visualPrompt)}&`;
    if (modelId) url += `model_id=${encodeURIComponent(modelId)}&`;
    
    const res = await fetch(url, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al generar miniatura');
    return res.json();
  }

  // YouTube Upload & SEO
  async getVideoMetadata(videoId: number): Promise<{
    title: string;
    description: string;
    tags: string;
    thumbnail_url: string;
    is_uploaded?: boolean;
    youtube_video_id?: string;
  }> {
    const res = await fetch(`${this.baseUrl}/youtube/${videoId}/metadata`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener metadatos');
    return res.json();
  }

  async uploadToYouTube(videoId: number, metadata: any): Promise<{ status: string, youtube_id: string }> {
    const res = await fetch(`${this.baseUrl}/youtube/${videoId}/upload`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify(metadata),
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Error al subir a YouTube');
    }
    return res.json();
  }

  async updateYouTubeMetadata(videoId: number, metadata: any): Promise<{ status: string }> {
    const res = await fetch(`${this.baseUrl}/youtube/${videoId}/update-metadata`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify(metadata),
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Error al actualizar YouTube');
    }
    return res.json();
  }

  async regenerateYoutubeTitle(videoId: number): Promise<{ title: string }> {
    const res = await fetch(`${this.baseUrl}/youtube/${videoId}/regenerate/title`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al regenerar título');
    return res.json();
  }

  async regenerateYoutubeDescription(videoId: number): Promise<{ description: string }> {
    const res = await fetch(`${this.baseUrl}/youtube/${videoId}/regenerate/description`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al regenerar descripción');
    return res.json();
  }

  async regenerateYoutubeTags(videoId: number): Promise<{ tags: string }> {
    const res = await fetch(`${this.baseUrl}/youtube/${videoId}/regenerate/tags`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al regenerar etiquetas');
    return res.json();
  }
}

export const api = new ApiClient();
