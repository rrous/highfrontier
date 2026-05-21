// Multiplayer presence abstraction — §4.
// Solo play calls nothing here. The interface is defined now so ui/ and game/
// only depend on this module, not on Supabase Realtime directly.

export interface PlayerPresence {
  id: string;
  x: number;  // map %
  y: number;  // map %
}

export interface PresenceChannel {
  join(position: { x: number; y: number }): void;
  move(position: { x: number; y: number }): void;
  leave(): void;
  onUpdate(cb: (players: PlayerPresence[]) => void): () => void;
}

// Stub — returns a no-op channel for solo play.
export function createPresenceChannel(_sessionId: string): PresenceChannel {
  const listeners: Array<(players: PlayerPresence[]) => void> = [];
  return {
    join() {},
    move() {},
    leave() {},
    onUpdate(cb) {
      listeners.push(cb);
      return () => { const i = listeners.indexOf(cb); if (i >= 0) listeners.splice(i, 1); };
    },
  };
}
