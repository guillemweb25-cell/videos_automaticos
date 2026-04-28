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
  llm_provider?: string;
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
  is_admin: boolean;
  credits: number;
}

export interface ChannelResponse {
  id: number;
  name: string;
  handle?: string;
  creds_dir?: string;
  image_style_prompt?: string;
  negative_prompt?: string;
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

  private getHeaders(auth = false, json = true) {
    const headers: any = {};
    if (json) {
      headers['Content-Type'] = 'application/json';
    }
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

  async getYouTubeInfo(id: number): Promise<any> {
    const response = await fetch(`${this.baseUrl}/channels/${id}/youtube/info`, {
      headers: this.getHeaders(true),
    });
    if (!response.ok) throw new Error("Failed to fetch YouTube info");
    return response.json();
  }

  async getYouTubeAuthUrl(id: number, redirectUri: string): Promise<{ auth_url: string }> {
    const response = await fetch(`${this.baseUrl}/channels/${id}/youtube/auth-url?redirect_uri=${encodeURIComponent(redirectUri)}`, {
      headers: this.getHeaders(true),
    });
    if (!response.ok) {
       const err = await response.json();
       throw new Error(err.detail || "Failed to get auth URL");
    }
    return response.json();
  }

  async finishYouTubeOAuth(id: number, code: string, redirectUri: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/channels/youtube/callback?code=${encodeURIComponent(code)}&channel_id=${id}&redirect_uri=${encodeURIComponent(redirectUri)}`, {
      method: "POST",
      headers: this.getHeaders(true),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to finish YouTube OAuth");
    }
    return response.json();
  }

  async uploadYouTubeClientSecret(id: number, file: File): Promise<any> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${this.baseUrl}/channels/${id}/youtube/client-secret`, {
      method: "POST",
      headers: this.getHeaders(true, false), // Added auth=true, json=false
      body: formData,
    });
    if (!response.ok) throw new Error("Failed to upload client secret");
    return response.json();
  }

  async deleteChannel(channelId: number): Promise<void> {
    const res = await fetch(`${this.baseUrl}/channels/${channelId}`, {
      method: 'DELETE',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al eliminar canal');
  }

  // Channel Music Methods
  async getChannelMusic(channelId: number): Promise<string[]> {
    const res = await fetch(`${this.baseUrl}/channels/${channelId}/music`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener lista de música');
    return res.json();
  }

  async uploadChannelMusic(channelId: number, file: File): Promise<{ ok: boolean, filename: string }> {
    const formData = new FormData();
    formData.append('file', file);
    
    const headers = this.getHeaders(true);
    // Remove Content-Type so browser sets boundaries for FormData
    delete headers['Content-Type'];
    
    const res = await fetch(`${this.baseUrl}/channels/${channelId}/music`, {
      method: 'POST',
      headers,
      body: formData,
    });
    if (!res.ok) throw new Error('Error al subir música');
    return res.json();
  }

  async deleteChannelMusic(channelId: number, filename: string): Promise<{ ok: boolean }> {
    const res = await fetch(`${this.baseUrl}/channels/${channelId}/music/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al eliminar música');
    return res.json();
  }

  getChannelMusicUrl(channelId: number, filename: string): string {
    const params = new URLSearchParams();
    const token = localStorage.getItem('token');
    if (token) {
        // Technically passing token in URL configures backend if it supports it, 
        // otherwise we might need a different auth mechanism for audio tag.
        // Actually since audio tag doesn't send Bearer easily, we can append token.
        params.append('token', token); 
    }
    return `${this.baseUrl}/channels/${channelId}/music/${encodeURIComponent(filename)}?${params.toString()}`;
  }

  // Style Guide Methods
  async checkStyleGuide(channelId: number): Promise<{ exists: boolean }> {
    const res = await fetch(`${this.baseUrl}/channels/${channelId}/style-guide`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al comprobar guía de estilo');
    return res.json();
  }

  async uploadStyleGuide(channelId: number, file: File): Promise<{ ok: boolean, filename: string }> {
    const formData = new FormData();
    formData.append('file', file);
    
    const headers = this.getHeaders(true);
    delete headers['Content-Type'];
    
    const res = await fetch(`${this.baseUrl}/channels/${channelId}/style-guide`, {
      method: 'POST',
      headers,
      body: formData,
    });
    if (!res.ok) throw new Error('Error al subir guía de estilo');
    return res.json();
  }

  async deleteStyleGuide(channelId: number): Promise<{ ok: boolean }> {
    const res = await fetch(`${this.baseUrl}/channels/${channelId}/style-guide`, {
      method: 'DELETE',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al eliminar guía de estilo');
    return res.json();
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

  async getOverlays(): Promise<{ overlays: string[] }> {
    const res = await fetch(`${this.baseUrl}/videos/overlays`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener overlays');
    return res.json();
  }

  async getWorkflows(): Promise<{ workflows: string[] }> {
    const res = await fetch(`${this.baseUrl}/videos/workflows`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener workflows');
    return res.json();
  }

  async createVideo(data: { channel_id: number; title: string; voice?: string; style?: string; width?: number; height?: number; max_images_per_paragraph?: number; llm_provider?: string }): Promise<VideoResponse> {
    const res = await fetch(`${this.baseUrl}/videos/`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      if (res.status === 402) {
        const err = await res.json();
        throw new Error(err.detail || 'INSUFFICIENT_CREDITS');
      }
      throw new Error('Error al crear vídeo');
    }
    return res.json();
  }

  async updateVideo(videoId: number, data: Partial<VideoResponse>): Promise<VideoResponse> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}`, {
      method: 'PATCH',
      headers: this.getHeaders(true),
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      if (res.status === 402) {
        const err = await res.json();
        throw new Error(err.detail || 'INSUFFICIENT_CREDITS');
      }
      throw new Error('Error al actualizar vídeo');
    }
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

  async resetImages(videoId: number): Promise<{ ok: boolean; message: string }> {
    const response = await fetch(`${this.baseUrl}/videos/${videoId}/reset-images`, {
      method: 'POST',
      headers: this.getHeaders(true)
    });
    if (!response.ok) throw new Error('Error al reiniciar el estado de imágenes');
    return response.json();
  }

  async generateImages(videoId: number, style: string, maxImages: number, modelId?: string, generationMode?: string, workflowName?: string): Promise<{ ok: boolean; count: number }> {
    const response = await fetch(`${this.baseUrl}/videos/${videoId}/images`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify({
        style_name: style,
        max_images_per_paragraph: maxImages,
        model_id: modelId,
        generation_mode: generationMode,
        workflow_name: workflowName
      })
    });

    if (!response.ok) throw new Error('Error al generar imágenes');
    const data = await response.json();

    
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

  private async pollVideoStatus(videoId: number, maxWaitMs = 1800000): Promise<{ ok: boolean; count: number }> {
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
    throw new Error('Image generation timed out after 30 minutes');

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

  async renderVideo(videoId: number, subtitles: boolean = false, overlay?: string): Promise<{ ok: boolean; output: string }> {
    const url = new URL(`${this.baseUrl}/videos/${videoId}/render`);
    if (subtitles) url.searchParams.append('subtitles', 'true');
    if (overlay) url.searchParams.append('overlay', overlay);
    
    const res = await fetch(url.toString(), {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Error al renderizar vídeo');
    }
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

  async addImage(videoId: number, paragraph_id: number, style?: string, modelId?: string, generationMode?: string, workflowName?: string): Promise<{ok: boolean, image: any}> {
    const response = await fetch(`${this.baseUrl}/videos/${videoId}/add-image`, {
      method: "POST",
      headers: this.getHeaders(true),
      body: JSON.stringify({
        paragraph_id,
        style_name: style,
        model_id: modelId,
        generation_mode: generationMode,
        workflow_name: workflowName
      })
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

  async convertImageToVideo(videoId: number, paragraphId: number, imageId: number, duration: number, modelId: string, customPrompt?: string): Promise<{ok: boolean, url: string}> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/image-to-video`, {
      method: "POST",
      headers: this.getHeaders(true),
      body: JSON.stringify({
        paragraph_id: paragraphId,
        image_id: imageId,
        duration: duration,
        model_id: modelId,
        custom_prompt: customPrompt
      })
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to convert image to video");
    }
    return res.json();
  }

  async linkClip(videoId: number, paragraphId: number, imageId: number, link: string): Promise<{ok: boolean, url: string}> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/link-clip`, {
      method: "POST",
      headers: this.getHeaders(true),
      body: JSON.stringify({
        paragraph_id: paragraphId,
        image_id: imageId,
        link: link
      })
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to link clip");
    }
    return res.json();
  }

  async uploadClip(videoId: number, paragraphId: number, imageId: number, file: File): Promise<{ok: boolean, url: string}> {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/upload-clip/${paragraphId}/${imageId}`, {
      method: "POST",
      headers: this.getHeaders(true, false),
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to upload clip");
    }
    return res.json();
  }

  async regenerateImage(videoId: number, paragraphId: number, imageId: number, customPrompt?: string, modelId?: string, generationMode?: string, workflowName?: string, seed?: number): Promise<{ ok: boolean, url: string }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/regenerate-image`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify({
        paragraph_id: paragraphId,
        image_id: imageId,
        custom_prompt: customPrompt,
        model_id: modelId,
        generation_mode: generationMode,
        workflow_name: workflowName,
        seed: seed
      })
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

  async generateThumbnail(videoId: number, hook?: string, visualPrompt?: string, modelId?: string, generationMode?: string): Promise<{ ok: boolean, url: string }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/generate-thumbnail`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify({
        hook,
        visual_prompt: visualPrompt,
        model_id: modelId,
        generation_mode: generationMode
      })
    });

    if (!res.ok) throw new Error('Error al generar miniatura');
    return res.json();
  }

  async updateThumbnailText(videoId: number, hook: string): Promise<{ ok: boolean, url: string }> {
    const res = await fetch(`${this.baseUrl}/videos/${videoId}/update-thumbnail-text`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify({ hook })
    });
    if (!res.ok) throw new Error('Error al actualizar texto de la miniatura');
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

  async regenerateYoutubeTitle(videoId: number, lang: string = "es", provider?: string): Promise<{ title: string }> {
    const url = new URL(`${this.baseUrl}/youtube/${videoId}/regenerate/title`);
    url.searchParams.append("lang", lang);
    if (provider) url.searchParams.append("provider", provider);

    const res = await fetch(url.toString(), {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al regenerar título');
    return res.json();
  }

  async regenerateYoutubeDescription(videoId: number, lang: string = "es", provider?: string): Promise<{ description: string }> {
    const url = new URL(`${this.baseUrl}/youtube/${videoId}/regenerate/description`);
    url.searchParams.append("lang", lang);
    if (provider) url.searchParams.append("provider", provider);

    const res = await fetch(url.toString(), {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al regenerar descripción');
    return res.json();
  }

  async regenerateYoutubeTags(videoId: number, lang: string = "es", provider?: string): Promise<{ tags: string }> {
    const url = new URL(`${this.baseUrl}/youtube/${videoId}/regenerate/tags`);
    url.searchParams.append("lang", lang);
    if (provider) url.searchParams.append("provider", provider);

    const res = await fetch(url.toString(), {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al regenerar etiquetas');
    return res.json();
  }

  async resetUploadState(videoId: number): Promise<{ status: string }> {
    const res = await fetch(`${this.baseUrl}/youtube/${videoId}/reset-upload`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Error al restablecer estado de subida');
    }
    return res.json();
  }

  // Settings Methods
  async getPublicSettings(): Promise<{ registration_enabled: boolean }> {
    const res = await fetch(`${this.baseUrl}/settings/public`, {
      headers: this.getHeaders(false),
    });
    if (!res.ok) throw new Error('Error al obtener ajustes generales');
    return res.json();
  }

  async updateGlobalSettings(data: { registration_enabled: boolean }): Promise<{ registration_enabled: boolean }> {
    const res = await fetch(`${this.baseUrl}/settings/global`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Error al actualizar ajustes generales');
    return res.json();
  }

  async getSettings(): Promise<{ has_openai: boolean, has_grok: boolean, has_leonardo: boolean, has_assemblyai: boolean, has_elevenlabs: boolean }> {
    const res = await fetch(`${this.baseUrl}/settings/`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener ajustes');
    return res.json();
  }

  async updateSettings(data: { 
    openai_api_key?: string, 
    grok_api_key?: string, 
    leonardo_api_key?: string, 
    assemblyai_api_key?: string, 
    elevenlabs_api_key?: string 
  }): Promise<{ has_openai: boolean, has_grok: boolean, has_leonardo: boolean, has_assemblyai: boolean, has_elevenlabs: boolean }> {
    const res = await fetch(`${this.baseUrl}/settings/`, {
      method: 'PUT',
      headers: this.getHeaders(true),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Error al actualizar ajustes');
    return res.json();
  }

  async cleanupCache(): Promise<{
    deleted_videos: number,
    freed_space_mb: number,
    optimized_images: number,
    image_reduction_mb: number,
    status: string
  }> {
    const res = await fetch(`${this.baseUrl}/settings/cleanup`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al limpiar caché');
    return res.json();
  }

  // Payment Methods
  async getBalance(): Promise<{ credits: number, euros: number }> {
    const res = await fetch(`${this.baseUrl}/payments/balance`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener saldo');
    return res.json();
  }

  async createCheckoutSession(amountEuros: number): Promise<{ checkout_url: string }> {
    const res = await fetch(`${this.baseUrl}/payments/create-checkout-session`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify({ amount_euros: amountEuros }),
    });
    if (!res.ok) throw new Error('Error al crear sesión de pago');
    return res.json();
  }
  // Admin Methods
  async adminGetUsers(): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/admin/users`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener usuarios (Admin)');
    return res.json();
  }

  async adminAddCredits(userId: number, amount: number): Promise<{ ok: boolean, new_balance: number }> {
    const res = await fetch(`${this.baseUrl}/admin/users/${userId}/add-credits`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify({ amount }),
    });
    if (!res.ok) throw new Error('Error al añadir créditos');
    return res.json();
  }

  async adminGetStats(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/admin/stats`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener estadísticas');
    return res.json();
  }
}

export const api = new ApiClient();
