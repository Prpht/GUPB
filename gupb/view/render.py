from __future__ import annotations
import os
import itertools
from typing import Any, Optional, TypeVar, Tuple

import pygame
import pygame.freetype

from gupb.controller import keyboard
from gupb.model import characters
from gupb.model import consumables
from gupb.model import effects
from gupb.model import games
from gupb.model import tiles
from gupb.model import weapons

pygame.init()

Sprite = TypeVar('Sprite')

INIT_TILE_SIZE = 32
KEEP_TILE_RATIO = False

HEALTH_BAR_HEIGHT = 4
HEALTH_BAR_UNIT_WIDTH = 2
HEALTH_BAR_FULL_COLOR = (250, 0, 0)
HEALTH_BAR_OVERFILL_COLOR = (150, 0, 0)
HEALTH_BAR_EMPTY_COLOR = (0, 0, 0)

BLACK = pygame.Color('black')
WHITE = pygame.Color('white')
GAME_FONT = pygame.freetype.Font("resources/fonts/whitrabt.ttf", 24)


def load_sprite(group: str, name: str, transparent: pygame.Color = None) -> Sprite:
    path = os.path.join('resources', 'images', group, f'{name}.png')
    sprite = pygame.image.load(path).convert()
    if sprite.get_size() is not (INIT_TILE_SIZE, INIT_TILE_SIZE):
        sprite = pygame.transform.scale(sprite, (INIT_TILE_SIZE, INIT_TILE_SIZE))
    if transparent:
        sprite.set_colorkey(transparent)
    return sprite


class SpriteRepository:
    def __init__(self) -> None:
        self.size = (INIT_TILE_SIZE, INIT_TILE_SIZE)
        self.sprites: dict[Any, Sprite] = {
            tiles.Sea: load_sprite('tiles', 'sea'),
            tiles.Land: load_sprite('tiles', 'land'),
            tiles.Forest: load_sprite('tiles', 'forest'),
            tiles.Wall: load_sprite('tiles', 'wall'),
            tiles.Menhir: load_sprite('tiles', 'menhir'),

            weapons.Knife: load_sprite('weapons', 'knife', BLACK),
            weapons.Sword: load_sprite('weapons', 'sword', BLACK),
            weapons.Axe: load_sprite('weapons', 'axe', BLACK),
            weapons.Bow: load_sprite('weapons', 'bow', BLACK),
            weapons.Amulet: load_sprite('weapons', 'amulet', BLACK),
            weapons.Scroll: load_sprite('weapons', 'scroll', BLACK),

            consumables.Potion: load_sprite('consumables', 'potion', BLACK),

            characters.Tabard.BLUE: load_sprite('characters', 'champion_blue', BLACK),
            characters.Tabard.BROWN: load_sprite('characters', 'champion_brown', BLACK),
            characters.Tabard.GREY: load_sprite('characters', 'champion_grey', BLACK),
            characters.Tabard.GREEN: load_sprite('characters', 'champion_green', BLACK),
            characters.Tabard.LIME: load_sprite('characters', 'champion_lime', BLACK),
            characters.Tabard.ORANGE: load_sprite('characters', 'champion_orange', BLACK),
            characters.Tabard.PINK: load_sprite('characters', 'champion_pink', BLACK),
            characters.Tabard.RED: load_sprite('characters', 'champion_red', BLACK),
            characters.Tabard.STRIPPED: load_sprite('characters', 'champion_stripped', BLACK),
            characters.Tabard.TURQUOISE: load_sprite('characters', 'champion_turquoise', BLACK),
            characters.Tabard.VIOLET: load_sprite('characters', 'champion_violet', BLACK),
            characters.Tabard.WHITE: load_sprite('characters', 'champion_white', BLACK),
            characters.Tabard.YELLOW: load_sprite('characters', 'champion_yellow', BLACK),
            characters.Tabard.NORGUL: load_sprite('characters', 'norgul', BLACK),
            characters.Tabard.KIRBY: load_sprite('characters', 'kirby', BLACK),
            characters.Tabard.KIMDZONGNEAT: load_sprite('characters', 'kim_dzong', BLACK),
            characters.Tabard.CAMPER: load_sprite('characters', 'champion_camper', BLACK),

            effects.Mist: load_sprite('effects', 'mist', BLACK),
            effects.WeaponCut: load_sprite('effects', 'blood', BLACK),
            effects.Fire: load_sprite('effects', 'fire', WHITE),
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
                    characters.Tabard.GREEN,
                    characters.Tabard.LIME,
                    characters.Tabard.ORANGE,
                    characters.Tabard.PINK,
                    characters.Tabard.RED,
                    characters.Tabard.STRIPPED,
                    characters.Tabard.TURQUOISE,
                    characters.Tabard.VIOLET,
                    characters.Tabard.WHITE,
                    characters.Tabard.YELLOW,
                    characters.Tabard.NORGUL
                    characters.Tabard.KIRBY,
                    characters.Tabard.KIMDZONGNEAT,
                    characters.Tabard.CAMPER,
                ],
                [
                    characters.Facing.RIGHT,
                    characters.Facing.UP,
                    characters.Facing.LEFT,
                    characters.Facing.DOWN,
                ]
            )
        }

        self._sprites = self.sprites.copy()
        self._champion_sprites = self.champion_sprites.copy()

    def match_sprite(self, element: Any) -> Sprite:
        if isinstance(element, characters.Champion):
            return self.champion_sprites[(element.tabard, element.facing)]
        else:
            return self.sprites[type(element)]

    @staticmethod
    def scale_sprite(sprite: Sprite, size: Tuple[int, int]) -> Sprite:
        return pygame.transform.scale(sprite, size)

    def scale_sprites(self, window_size: Tuple[int, int], arena_size: Tuple[int, int]) -> Tuple[int, int]:
        self.size = (int(window_size[0] / arena_size[0]), int(window_size[1] / arena_size[1]))

        if KEEP_TILE_RATIO:
            self.size = (min(self.size), min(self.size))

        for sprite in self.sprites:
            self.sprites[sprite] = self.scale_sprite(self._sprites[sprite], self.size)

        for sprite in self.champion_sprites:
            self.champion_sprites[sprite] = self.scale_sprite(self._champion_sprites[sprite], self.size)

        return self.size[0] * arena_size[0], self.size[1] * arena_size[1]


class Renderer:
    def __init__(self, ms_per_time_unit: int = 5):
        pygame.display.set_caption('GUPB')
        self.screen = pygame.display.set_mode((500, 500), pygame.RESIZABLE)
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
        self._render_starting_screen()

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
                if event.type == pygame.VIDEORESIZE:
                    new_size = self.sprite_repository.scale_sprites((event.w, event.h), game.arena.size)
                    self.screen = pygame.display.set_mode(new_size, pygame.RESIZABLE)

    def _resize_window(self, game: games.Game) -> pygame.Surface:
        arena_x_size, arena_y_size = game.arena.size
        window_size = self.sprite_repository.size[0] * arena_x_size, self.sprite_repository.size[1] * arena_y_size
        return pygame.display.set_mode(window_size, pygame.RESIZABLE)

    def _time_to_cycle(self, game: games.Game) -> int:
        return self.ms_per_time_unit * game.current_state.value

    def _render_starting_screen(self):
        wait_for_start_key = True
        while wait_for_start_key:
            GAME_FONT.render_to(self.screen, (70, 180), "Press X to start..!", (250, 250, 250))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_x:
                    wait_for_start_key = False

    def _render(self, game: games.Game, show_sight: Optional[characters.Champion]) -> None:
        background = pygame.Surface(self.screen.get_size())
        background.convert()
        self._render_arena(game, background)
        if show_sight:
            self._render_sight(game, show_sight, background)
        self.screen.blit(background, (0, 0))
        pygame.display.flip()

    def _render_arena(self, game: games.Game, background: pygame.Surface) -> None:
        def render_character() -> None:
            def prepare_heath_bar_rect(health: int) -> pygame.Rect:
                return pygame.Rect(
                    blit_destination[0],
                    blit_destination[1] - HEALTH_BAR_HEIGHT - 1,
                    health * HEALTH_BAR_UNIT_WIDTH,
                    HEALTH_BAR_HEIGHT
                )

            character_sprite = self.sprite_repository.match_sprite(tile.character)
            background.blit(character_sprite, blit_destination)
            pygame.draw.rect(
                background,
                HEALTH_BAR_OVERFILL_COLOR,
                prepare_heath_bar_rect(tile.character.health)
            )
            pygame.draw.rect(
                background,
                HEALTH_BAR_EMPTY_COLOR,
                prepare_heath_bar_rect(characters.CHAMPION_STARTING_HP)
            )
            pygame.draw.rect(
                background,
                HEALTH_BAR_FULL_COLOR,
                prepare_heath_bar_rect(min(characters.CHAMPION_STARTING_HP, tile.character.health))
            )

        for i, j in game.arena.terrain:
            blit_destination = (i * self.sprite_repository.size[0], j * self.sprite_repository.size[1])
            tile = game.arena.terrain[i, j]
            tile_sprite = self.sprite_repository.match_sprite(tile)
            background.blit(tile_sprite, blit_destination)
            if tile.loot:
                loot_sprite = self.sprite_repository.match_sprite(tile.loot)
                background.blit(loot_sprite, blit_destination)
            if tile.consumable:
                consumable_sprite = self.sprite_repository.match_sprite(tile.consumable)
                background.blit(consumable_sprite, blit_destination)
            if tile.character:
                render_character()
            if tile.effects:
                for effect in tile.effects:
                    effect_sprite = self.sprite_repository.match_sprite(effect)
                    background.blit(effect_sprite, blit_destination)

    def _render_sight(self, game: games.Game, show_sight: characters.Champion, background: pygame.Surface) -> None:
        if show_sight in game.champions:
            darken_percent = 0.5
            dark = pygame.Surface(self.sprite_repository.size, pygame.SRCALPHA)
            dark.fill((0, 0, 0, int(darken_percent * 255)))
            visible = game.arena.visible_coords(show_sight)
            for i, j in game.arena.terrain:
                if (i, j) not in visible:
                    blit_destination = (i * self.sprite_repository.size[0], j * self.sprite_repository.size[1])
                    background.blit(dark, blit_destination)
