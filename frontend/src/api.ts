const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface LoginResponse {
  access_token: string;
  token_type: string;
}

interface UserResponse {
  id: number;
  email: string;
  is_active: boolean;
  created_at: string;
}

interface ChannelResponse {
  id: number;
  name: string;
  youtube_handle: string | null;
  creds_dir: string | null;
  user_id: number;
  created_at: string;
}

interface ChannelUpdate {
  name?: string;
  youtube_handle?: string;
  creds_dir?: string;
}

interface YouTubeChannelInfo {
  snippet: {
    title: string;
    description: string;
    thumbnails: {
      default: { url: string };
      medium: { url: string };
    };
  };
  statistics: {
    viewCount: string;
    subscriberCount: string;
    videoCount: string;
  };
}

interface YouTubeVideo {
  id: string;
  title: string;
  thumbnail: string;
  published_at: string;
  view_count?: string;
  duration_seconds?: number;
}

class ApiClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_URL;
  }

  private getHeaders(auth = false): HeadersInit {
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

  async register(email: string, password: string): Promise<UserResponse> {
    const res = await fetch(`${this.baseUrl}/auth/register`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Error en el registro');
    }
    return res.json();
  }

  async login(email: string, password: string): Promise<LoginResponse> {
    const res = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Error en el login');
    }
    const data: LoginResponse = await res.json();
    localStorage.setItem('token', data.access_token);
    return data;
  }

  async getMe(): Promise<UserResponse> {
    const res = await fetch(`${this.baseUrl}/auth/me`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) {
      localStorage.removeItem('token');
      throw new Error('No autenticado');
    }
    return res.json();
  }

  logout(): void {
    localStorage.removeItem('token');
  }

  // --- Channels ---

  async getChannels(): Promise<ChannelResponse[]> {
    const res = await fetch(`${this.baseUrl}/channels/`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener canales');
    return res.json();
  }

  async createChannel(name: string, youtube_handle?: string): Promise<ChannelResponse> {
    const res = await fetch(`${this.baseUrl}/channels/`, {
      method: 'POST',
      headers: this.getHeaders(true),
      body: JSON.stringify({ name, youtube_handle }),
    });
    if (!res.ok) throw new Error('Error al crear canal');
    return res.json();
  }

  async deleteChannel(id: number): Promise<void> {
    const res = await fetch(`${this.baseUrl}/channels/${id}`, {
      method: 'DELETE',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al eliminar canal');
  }

  async updateChannel(id: number, data: ChannelUpdate): Promise<ChannelResponse> {
    const res = await fetch(`${this.baseUrl}/channels/${id}`, {
      method: 'PATCH',
      headers: this.getHeaders(true),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Error al actualizar canal');
    return res.json();
  }

  // --- YouTube ---

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
    if (!res.ok) throw new Error('Error al obtener vídeos');
    return res.json();
  }

  async getYouTubeShorts(channelId: number): Promise<YouTubeVideo[]> {
    const res = await fetch(`${this.baseUrl}/youtube/shorts/${channelId}`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener shorts');
    return res.json();
  }

  async downloadYouTubeAudio(channelId: number, url: string): Promise<{ status: string, path: string }> {
    const res = await fetch(`${this.baseUrl}/youtube/download/${channelId}?url=${encodeURIComponent(url)}`, {
      method: 'POST',
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al iniciar descarga');
    return res.json();
  }

  async getDownloadedFiles(channelId: number): Promise<string[]> {
    const res = await fetch(`${this.baseUrl}/youtube/downloads/${channelId}`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) throw new Error('Error al obtener descargas');
    return res.json();
  }
}

export const api = new ApiClient();
export type { LoginResponse, UserResponse, ChannelResponse, YouTubeChannelInfo, YouTubeVideo };
