'use client';
/**
 * Context a dashboard grid gives to each widget slot. A `Card` rendered inside it becomes a grid
 * widget: it takes its span from the layout and, while the grid is movable, its header is a grip
 * (drag to move), a small grabber at its top edge is the keyboard handle (arrows move) and a corner
 * handle resizes. Outside a grid the context is null and Card is unchanged.
 */
import { createContext, useContext, type KeyboardEvent, type PointerEvent } from 'react';

export interface WidgetChrome {
  id: string;
  w: number;
  h: number;
  /** Move and resize available (false when the grid stacks into one column). */
  movable: boolean;
  dragging: boolean;
  resizing: boolean;
  /** Visible title, used in handle labels ("Move Allocation"). */
  title: string;
  /** Label of this widget in the section dock. */
  section?: string;
  /** Widget whose content draws its own tiles (no card sheet behind it). */
  bare?: boolean;
  onMovePointerDown: (event: PointerEvent<HTMLElement>) => void;
  onMoveKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
  onResizePointerDown: (event: PointerEvent<HTMLElement>) => void;
  onResizeKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
}

export const WidgetContext = createContext<WidgetChrome | null>(null);

export function useWidget(): WidgetChrome | null {
  return useContext(WidgetContext);
}
