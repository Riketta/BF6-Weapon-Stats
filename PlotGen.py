import argparse
import math
import csv
import matplotlib.pyplot as plt
from enum import StrEnum
from itertools import cycle


HEALTH = 100
STATS_FILE = "Stats.csv"
DISTANCES = [
    "0 m",
    "10 m",
    # "15 m",  # Same as previous.
    "20 m",
    # "25 m",  # Same as previous.
    # "35 m",  # Same as previous.
    "40 m",
    # "50 m",  # Same as previous.
    # "55 m",  # Same as previous.
    # "70 m",  # Same as previous.
    "70+ m",
]


class WeaponClass(StrEnum):
    All = "All"
    AR = "AR"
    Carbine = "Carbine"
    SMG = "SMG"
    LMG = "LMG"


class TtkType(StrEnum):
    Unknown = "Unknown"
    Body = "Body"
    SingleHS = "1HS"


class Weapon:
    def __init__(self, row):
        self.Name = row["Weapon"]
        self.Class = row["Class"]
        self.HeadshotMultiplier = float(row["HS Mult"])
        self.RPM = int(row["RPM"])
        self.ShotIntverval = 60_000 / self.RPM

        self.DamageFalloffs = []
        for distance in DISTANCES:
            self.DamageFalloffs.append(float(row[distance]))

    def TTK_AllBody(self):
        ttk = []
        for damage in self.DamageFalloffs:
            body_shots = math.ceil(HEALTH / damage)
            ttk_body = (body_shots - 1) * self.ShotIntverval
            ttk.append(ttk_body)
        return ttk

    def TTK_1HS_Body(self):
        ttk = []
        for damage in self.DamageFalloffs:
            remaining_health = HEALTH - (damage * self.HeadshotMultiplier)
            body_shots = math.ceil(remaining_health / damage)
            ttk_body = (body_shots - 1 + 1) * self.ShotIntverval
            ttk.append(ttk_body)
        return ttk


def read_weapon_stats():
    weapons = []
    with open(STATS_FILE) as csvfile:
        weapon_stats_reader = csv.DictReader(csvfile)
        for row in weapon_stats_reader:
            # print(row)
            weapon = Weapon(row)
            weapons.append(weapon)
    return weapons


def plot(weapons, y_strategy, strategy_name="Default", fixed_ticks=False):
    plt.figure(figsize=(10, 6))
    line_styles = cycle([":", "-."])
    for weapon in weapons:
        y = y_strategy(weapon)
        # y.insert(0, y[0])
        y.append(y[-1])
        x = list(range(len(y)))

        # plt.plot(x, y, marker="o", label=weapon.Name)
        plt.step(
            x,
            y,
            where="post",
            marker="o",
            label=weapon.Name,
            linestyle=next(line_styles),
            alpha=0.75,
        )
    plt.title(
        "BF6 Weapons - TTK ({strategy_name}) vs Distance".format(
            strategy_name=strategy_name
        )
    )
    plt.xlabel("Distance")
    # DISTANCES.insert(0, "")
    plt.xticks(range(len(DISTANCES)), DISTANCES, rotation=45)
    plt.ylabel("TTK (ms)")
    if fixed_ticks:
        plt.yticks(range(50, 600, 50))
    plt.legend(fontsize=8, bbox_to_anchor=(1.02, 1), loc="upper left")
    # plt.grid(True, which="major", linestyle="--", linewidth=0.50, alpha=0.85)
    plt.tight_layout()
    plt.show()


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "-c", "--class", dest="weapon_class", default=WeaponClass.All
    )
    argparser.add_argument("-t", "--ttk", dest="ttk_model", default=TtkType.Body)
    args = argparser.parse_args()

    weapon_class = args.weapon_class
    ttk_model = args.ttk_model

    all_weapons = read_weapon_stats()

    weapons_to_plot = []
    if weapon_class == WeaponClass.All:
        weapons_to_plot = all_weapons
    else:
        for weapon in all_weapons:
            if weapon.Class == weapon_class:
                weapons_to_plot.append(weapon)

    y_strategy = None
    y_strategy_name = TtkType.Unknown
    if ttk_model == TtkType.Body:
        y_strategy = Weapon.TTK_AllBody
        y_strategy_name = "All Body"
    elif ttk_model == TtkType.SingleHS:
        y_strategy = Weapon.TTK_1HS_Body
        y_strategy_name = "1 HS + Body"

    plot(weapons_to_plot, y_strategy, strategy_name=y_strategy_name)


if __name__ == "__main__":
    main()
