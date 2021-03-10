from __future__ import annotations
import os
import itertools
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
        self.sprites: dict[Any, Sprite] = {
            tiles.Land: load_sprite('tiles', 'land'),
            tiles.Sea: load_sprite('tiles', 'sea'),
            tiles.Wall: load_sprite('tiles', 'wall'),
            tiles.Menhir: load_sprite('tiles', 'menhir'),

            weapons.Knife: load_sprite('weapons', 'knife', BLACK),
            weapons.Sword: load_sprite('weapons', 'sword', BLACK),
            weapons.Axe: load_sprite('weapons', 'axe', BLACK),
            weapons.Bow: load_sprite('weapons', 'bow', BLACK),
            weapons.Amulet: load_sprite('weapons', 'amulet', BLACK),

            characters.Tabard.BLUE: load_sprite('characters', 'champion_blue', BLACK),
            characters.Tabard.BROWN: load_sprite('characters', 'champion_brown', BLACK),
            characters.Tabard.GREY: load_sprite('characters', 'champion_grey', BLACK),
            characters.Tabard.RED: load_sprite('characters', 'champion_red', BLACK),
            characters.Tabard.VIOLET: load_sprite('characters', 'champion_violet', BLACK),
            characters.Tabard.WHITE: load_sprite('characters', 'champion_white', BLACK),
            characters.Tabard.YELLOW: load_sprite('characters', 'champion_yellow', BLACK),

            effects.Mist: load_sprite('effects', 'mist', BLACK),
            effects.WeaponCut: load_sprite('effects', 'blood', BLACK),
        }
        self.rotation_values: dict[characters.Facing, int] = {
            characters.Facing.RIGHT: 0,
            characters.Facing.UP: 90,
            characters.Facing.LEFT: 180,
            characters.Facing.DOWN: 270,
        }
        self.champion_sprites: dict[tuple[characters.Tabard, characters.Facing], Sprite] = {
            (tabard, facing): pygame.transform.rotate(self.sprites[tabard], self.rotation_values[facing])
            for tabard, facing in itertools.product(
                [
                    characters.Tabard.BLUE,
                    characters.Tabard.BROWN,
                    characters.Tabard.GREY,
                    characters.Tabard.RED,
                    characters.Tabard.VIOLET,
                    characters.Tabard.WHITE,
                    characters.Tabard.YELLOW,
                ],
                [
                    characters.Facing.RIGHT,
                    characters.Facing.UP,
                    characters.Facing.LEFT,
                    characters.Facing.DOWN,
                ]
            )
        }

    def match_sprite(self, element: Any) -> Sprite:
        if isinstance(element, characters.Champion):
            return self.champion_sprites[(element.tabard, element.facing)]
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
