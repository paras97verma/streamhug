/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module '*.css' {
  const content: string;
  export default content;
}

declare module 'vidstack/player' {}
declare module 'vidstack/player/layouts/default' {}
declare module 'vidstack/player/ui' {}

declare module 'vidstack/elements' {
  export interface MediaPlayerElement extends HTMLElement {
    duration: number;
    currentTime: number;
    destroy: () => void;
  }
}
