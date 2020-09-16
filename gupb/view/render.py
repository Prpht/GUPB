from __future__ import annotations
import os
from typing import Any, Optional, TypeVar

import pygame

from gupb.controller import keyboard
from gupb.model import characters
from gupb.model import effects
from gupb.model import games
from gupb.model import tiles
from gupb.model import weapons

pygame.init()

Sprite = TypeVar('Sprite')

TILE_SIZE = 8
BLACK = pygame.Color('black')


def load_sprite(group: str, name: str, transparent: pygame.Color = None) -> Sprite:
    path = os.path.join('resources', 'images', group, f'{name}.png')
    sprite = pygame.image.load(path).convert()
    if transparent:
        sprite.set_colorkey(transparent)
    return sprite


class SpriteRepository:
    def __init__(self) -> None:
        self.sprites: dict[type, Sprite] = {
            tiles.Land: load_sprite('tiles', 'land'),
            tiles.Sea: load_sprite('tiles', 'sea'),
            tiles.Wall: load_sprite('tiles', 'wall'),
            tiles.Menhir: load_sprite('tiles', 'menhir'),

            weapons.Knife: load_sprite('weapons', 'knife', BLACK),
            weapons.Sword: load_sprite('weapons', 'sword', BLACK),
            weapons.Axe: load_sprite('weapons', 'axe', BLACK),
            weapons.Bow: load_sprite('weapons', 'bow', BLACK),
            weapons.Amulet: load_sprite('weapons', 'amulet', BLACK),

            characters.Champion: load_sprite('characters', 'champion', BLACK),

            effects.Mist: load_sprite('effects', 'mist', BLACK),
            effects.WeaponCut: load_sprite('effects', 'blood', BLACK),
        }
        self.champion_sprites: dict[characters.Facing, Sprite] = {
            characters.Facing.RIGHT: self.sprites[characters.Champion],
            characters.Facing.UP: pygame.transform.rotate(self.sprites[characters.Champion], 90),
            characters.Facing.LEFT: pygame.transform.rotate(self.sprites[characters.Champion], 180),
            characters.Facing.DOWN: pygame.transform.rotate(self.sprites[characters.Champion], 270),
        }

    def match_sprite(self, element: Any) -> Sprite:
        if isinstance(element, characters.Champion):
            return self.champion_sprites[element.facing]
        else:
            return self.sprites[type(element)]


class Renderer:
    def __init__(self, ms_per_time_unit: int = 1):
        pygame.display.set_caption('GUPB')
        self.screen = pygame.display.set_mode((100, 100))
        self.sprite_repository = SpriteRepository()
        self.clock = pygame.time.Clock()
        self.time_passed = 0
        self.ms_per_time_unit = ms_per_time_unit

    def run(
            self,
            game: games.Game,
            show_sight: Optional[characters.Champion] = None,
            keyboard_controller: Optional[keyboard.KeyboardController] = None,
    ) -> None:
        self.screen = self._resize_window(game)

        time_to_cycle = self._time_to_cycle(game)
        self.clock.tick()
        while not game.finished:
            self.time_passed += self.clock.tick()
            if self.time_passed >= time_to_cycle:
                self.time_passed -= time_to_cycle
                game.cycle()
                self._render(game, show_sight)
                time_to_cycle = self._time_to_cycle(game)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.KEYDOWN and keyboard_controller:
                    keyboard_controller.register(event.key)

    @staticmethod
    def _resize_window(game: games.Game) -> pygame.Surface:
        arena_x_size, arena_y_size = game.arena.size
        window_size = TILE_SIZE * arena_x_size, TILE_SIZE * arena_y_size
        return pygame.display.set_mode(window_size)

    def _time_to_cycle(self, game: games.Game) -> int:
        return self.ms_per_time_unit * game.current_state.value

    def _render(self, game: games.Game, show_sight: Optional[characters.Champion]) -> None:
        background = pygame.Surface(self.screen.get_size())
        background.convert()
        self._render_arena(game, background)
        if show_sight:
            self._render_sight(game, show_sight, background)
        self.screen.blit(background, (0, 0))
        pygame.display.flip()

    def _render_arena(self, game: games.Game, background: pygame.Surface) -> None:
        for i, j in game.arena.terrain:
            blit_destination = (i * TILE_SIZE, j * TILE_SIZE)
            tile = game.arena.terrain[i, j]
            tile_sprite = self.sprite_repository.match_sprite(tile)
            background.blit(tile_sprite, blit_destination)
            if tile.loot:
                loot_sprite = self.sprite_repository.match_sprite(tile.loot)
                background.blit(loot_sprite, blit_destination)
            if tile.character:
                character_sprite = self.sprite_repository.match_sprite(tile.character)
                background.blit(character_sprite, blit_destination)
            if tile.effects:
                for effect in tile.effects:
                    effect_sprite = self.sprite_repository.match_sprite(effect)
                    background.blit(effect_sprite, blit_destination)

    @staticmethod
    def _render_sight(game: games.Game, show_sight: characters.Champion, background: pygame.Surface) -> None:
        if show_sight in game.champions:
            darken_percent = 0.5
            dark = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            dark.fill((0, 0, 0, darken_percent * 255))
            visible = game.arena.visible_coords(show_sight)
            for i, j in game.arena.terrain:
                if (i, j) not in visible:
                    blit_destination = (i * TILE_SIZE, j * TILE_SIZE)
                    background.blit(dark, blit_destination)
