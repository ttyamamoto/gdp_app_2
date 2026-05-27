import pandas as pd
import matplotlib.pyplot as plt
import japanize_matplotlib

# 日本語フォントの設定（環境に合わせて変更してください。Windowsなら 'MS Gothic' 等）
# plt.rcParams['font.family'] = 'sans-serif'
# plt.rcParams['font.family'] = 'Source Han Code JP'
# plt.rcParams["font.family"] = "MS Gothic"
plt.rcParams["font.family"] = "IPAexGothic"

def plot_macro_trends():
    try:
        df = pd.read_csv(d0 + "age01_macro_data_v1.2.csv")
    except FileNotFoundError:
        print("エラー: macro_data_v1.2.csv が見つかりません。")
        return

    plt.figure(figsize=(10, 5))
    plt.plot(df["Month"], df["C_Total"], label="民間消費 (C_Total)", marker='o', linewidth=2)
    plt.plot(df["Month"], df["C_Basic"], label="C_Basic (生活必需品)", marker='o', linewidth=1)
    plt.plot(df["Month"], df["C_Luxury"], label="C_Luxury (嗜好品)", marker='o', linewidth=1)
    plt.plot(df["Month"], df["G"], label="政府支出 (G)", marker='s', linewidth=2)
    plt.plot(df["Month"], df["GDP"], label="総生産 (GDP)", marker='^', linestyle='--', color='black')

    plt.title("マクロ経済の推移 (GDPと構成要素)")
    plt.xlabel("月 (Month)")
    plt.ylabel("貨幣量 (単位)")
    plt.xticks(df["Month"])
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig(d1 + "plot_macro_trends.png")
    plt.show()

def plot_wealth_distribution():
    try:
        df = pd.read_csv(d0 + "age01_wealth_distribution_v1.2.csv")
    except FileNotFoundError:
        return

    plt.figure(figsize=(8, 6))
    levels = sorted(df["Hierarchy_Level"].unique())
    data_by_level = [df[df["Hierarchy_Level"] == lvl]["Final_Assets"] for lvl in levels]
    plt.boxplot(data_by_level, labels=[f"階層 {lvl}\n(社長級 -> 平社員)" for lvl in levels])

    plt.title("シミュレーション終了時の家計資産分布 (富の偏在)")
    plt.xlabel("企業の役職階層")
    plt.ylabel("最終的な預金残高 (資産)")
    plt.grid(axis='y', linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(d1 + "plot_wealth_distribution.png")
    plt.show()

def plot_apc_trends():
    try:
        df = pd.read_csv(d0 + "age01_apc_data_v1.2.csv")
    except FileNotFoundError:
        return

    # グラフ1: 全家計のAPC推移
    plt.figure(figsize=(12, 6))
    for hh_id in df["Household_ID"].unique():
        hh_data = df[df["Household_ID"] == hh_id]
        level = hh_data["Hierarchy_Level"].iloc[0]
        color = 'red' if level == 0 else ('green' if level == 1 else 'blue')
        plt.plot(hh_data["Month"], hh_data["APC"], color=color, alpha=0.15, linewidth=1)

    plt.title("全家計の平均消費性向 (APC) の推移")
    plt.xlabel("月 (Month)")
    plt.ylabel("平均消費性向 (消費額 ÷ 収入額)")
    plt.xticks(df["Month"].unique())
    plt.ylim(0, df["APC"].max() * 1.1)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(d1 + "plot_apc_all_households.png")
    plt.show()

    # グラフ2: 階層ごとの加重平均APC推移
    plt.figure(figsize=(10, 5))
    grouped = df.groupby(["Month", "Hierarchy_Level"])[["Income", "Consumption_Money"]].sum()
    grouped["Weighted_APC"] = grouped["Consumption_Money"] / grouped["Income"]
    df_weighted_apc = grouped["Weighted_APC"].unstack()

    for level in df_weighted_apc.columns:
        plt.plot(df_weighted_apc.index, df_weighted_apc[level], label=f"階層 {level}", marker='o', linewidth=2)

    plt.title("階層ごとの平均消費性向 (加重平均) の推移")
    plt.xlabel("月 (Month)")
    plt.ylabel("加重平均消費性向")
    plt.xticks(df_weighted_apc.index)
    plt.ylim(0, df_weighted_apc.max().max() * 1.1)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(title="企業の役職階層")
    plt.tight_layout()
    plt.savefig(d1 + "plot_apc_weighted_average.png")
    plt.show()

def plot_firm_sales_trends():
    try:
        df = pd.read_csv(d0 + "age01_firm_sales_data_v1.2.csv")
    except FileNotFoundError:
        return

    plt.figure(figsize=(12, 6))
    for firm_id in df["Firm_ID"].unique():
        firm_data = df[df["Firm_ID"] == firm_id]
        is_g_target = str(firm_data["Is_G_Target"].iloc[0]).lower() == "true"
        if is_g_target:
            plt.plot(firm_data["Month"], firm_data["Revenue"], label=f"{firm_id}", color='red', marker='o', linewidth=2)
        else:
            plt.plot(firm_data["Month"], firm_data["Revenue"], label=f"{firm_id}", color='blue', marker='x', linewidth=1, alpha=0.6)

    plt.title("各企業の月間売上高の推移")
    plt.xlabel("月 (Month)")
    plt.ylabel("月間売上高 (Revenues)")
    plt.xticks(df["Month"].unique())
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(d1 + "plot_firm_sales_trends.png")
    plt.show()

# --- 新規追加: 企業在庫の推移グラフ ---
def plot_inventory_trends():
    """各企業の月末在庫数量（売れ残り）の時系列推移をプロット"""
    try:
        df = pd.read_csv(d0 + "age01_firm_sales_data_v1.2.csv")
        # Inventory_Basic列があるか確認
        if "Inventory_Basic" not in df.columns:
            print("エラー: csvファイルにInventory列がありません。main.pyを最新版で再実行してください。")
            return
    except FileNotFoundError:
        print("エラー: age01_firm_sales_data_v1.2.csv が見つかりません。")
        return

    # 1. 必需品在庫 (Inventory_Basic) のプロット
    plt.figure(figsize=(12, 5))
    for firm_id in df["Firm_ID"].unique():
        firm_data = df[df["Firm_ID"] == firm_id]
        is_g_target = str(firm_data["Is_G_Target"].iloc[0]).lower() == "true"
        color = 'red' if is_g_target else 'blue'
        if firm_id == "企業_1(G・C対象)": color = 'black'
        plt.plot(firm_data["Month"], firm_data["Inventory_Basic"], label=f"{firm_id}", color=color, alpha=0.6)

    plt.title("各企業の必需品在庫 (Inventory_Basic) の推移 (月末の売れ残り量)")
    plt.xlabel("月 (Month)")
    plt.ylabel("在庫数量")
    plt.xticks(df["Month"].unique())
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(d1 + "plot_inventory_basic_trends.png")
    plt.show()

    # 2. 嗜好品在庫 (Inventory_Luxury) のプロット
    plt.figure(figsize=(12, 5))
    for firm_id in df["Firm_ID"].unique():
        firm_data = df[df["Firm_ID"] == firm_id]
        is_g_target = str(firm_data["Is_G_Target"].iloc[0]).lower() == "true"
        color = 'red' if is_g_target else 'green'
        if firm_id == "企業_1(G・C対象)": color = 'black'
        plt.plot(firm_data["Month"], firm_data["Inventory_Luxury"], label=f"{firm_id}", color=color, alpha=0.6)

    plt.title("各企業の嗜好品在庫 (Inventory_Luxury) の推移 (月末の売れ残り量)")
    plt.xlabel("月 (Month)")
    plt.ylabel("在庫数量")
    plt.xticks(df["Month"].unique())
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(d1 + "plot_inventory_luxury_trends.png")
    plt.show()

def plot_price_trends():
    """各企業の必需品価格と嗜好品価格の時系列推移をプロット"""
    try:
        # csvファイル名に _v1.2 が付いている点に注意してください
        df = pd.read_csv(d0 + "age01_firm_sales_data_v1.2.csv")
        if "Price_Basic" not in df.columns:
            print("エラー: csvファイルにPrice列がありません。")
            return
    except FileNotFoundError:
        print("エラー: age01_firm_sales_data_v1.2.csv が見つかりません。")
        return

    # 1. 必需品価格 (Price_Basic) のプロット
    plt.figure(figsize=(12, 5))
    for firm_id in df["Firm_ID"].unique():
#    for firm_id in ["企業_1(G・C対象)"]:
#        if firm_id == "企業_1(G・C対象)":
#            continue
        firm_data = df[df["Firm_ID"] == firm_id]
        is_g_target = str(firm_data["Is_G_Target"].iloc[0]).lower() == "true"

        # 政府事業受注企業は赤、一般企業は青
        color = 'red' if is_g_target else 'blue'
        if firm_id == "企業_1(G・C対象)": color = 'black'
        plt.plot(firm_data["Month"], firm_data["Price_Basic"], label=f"{firm_id}", color=color, alpha=0.6)

    plt.title("各企業の必需品価格 (Price_Basic) の推移")
    plt.xlabel("月 (Month)")
    plt.ylabel("価格 (1単位あたり)")
    plt.xticks(df["Month"].unique())
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(d1 + "plot_price_basic_trends.png")
    plt.show()

    # 2. 嗜好品価格 (Price_Luxury) のプロット
    plt.figure(figsize=(12, 5))
    for firm_id in df["Firm_ID"].unique():
        firm_data = df[df["Firm_ID"] == firm_id]
        is_g_target = str(firm_data["Is_G_Target"].iloc[0]).lower() == "true"

        # 政府事業受注企業は赤、一般企業は緑
        color = 'red' if is_g_target else 'green'
        if firm_id == "企業_1(G・C対象)": color = 'black'
        plt.plot(firm_data["Month"], firm_data["Price_Luxury"], label=f"{firm_id}", color=color, alpha=0.6)

    plt.title("各企業の嗜好品価格 (Price_Luxury) の推移")
    plt.xlabel("月 (Month)")
    plt.ylabel("価格 (1単位あたり)")
    plt.xticks(df["Month"].unique())
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(d1 + "plot_price_luxury_trends.png")
    plt.show()

def plot_income_trends():
    """全家計および階層ごとの月間収入の時系列推移をプロット"""
    try:
        df = pd.read_csv(d0 + "age01_apc_data_v1.2.csv")
    except FileNotFoundError:
        print("エラー: age01_apc_data_v1.2.csv が見つかりません。")
        return

    # === グラフ1: 全家計の収入推移 ===
    plt.figure(figsize=(12, 6))

    for hh_id in df["Household_ID"].unique():
        hh_data = df[df["Household_ID"] == hh_id]
        level = hh_data["Hierarchy_Level"].iloc[0]

        color = 'red' if level == 0 else ('green' if level == 1 else 'blue')
        plt.plot(hh_data["Month"], hh_data["Income"], color=color, alpha=0.15, linewidth=1)

    plt.title("全家計の月間収入の推移 (赤:階層0, 緑:階層1, 青:階層2)")
    plt.xlabel("月 (Month)")
    plt.ylabel("月間収入 (Income)")
    plt.xticks(df["Month"].unique())

    # y軸の下限を0に設定（もし対数スケールにしたい場合は下の行をアンコメントしてください）
    #plt.ylim(bottom=0)
    plt.yscale('log') # 階層間の差が大きすぎる場合は対数軸が便利です

    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(d1 + "plot_income_all_households.png")
    plt.show()

    # === グラフ2: 階層ごとの「平均収入」推移 ===
    plt.figure(figsize=(10, 5))

    # 各月・各階層ごとに収入の平均値を算出
    grouped = df.groupby(["Month", "Hierarchy_Level"])["Income"].mean()
    df_mean_income = grouped.unstack()

    # 階層ごとに太い折れ線グラフを描画
    for level in df_mean_income.columns:
        plt.plot(df_mean_income.index, df_mean_income[level], label=f"階層 {level}", marker='o', linewidth=2)

    plt.title("階層ごとの平均月間収入の推移")
    plt.xlabel("月 (Month)")
    plt.ylabel("平均月間収入")
    plt.xticks(df_mean_income.index)

    #plt.ylim(bottom=0)
    plt.yscale('log') # こちらも対数軸に切り替え可能です

    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(title="企業の役職階層")
    plt.tight_layout()
    plt.savefig(d1 + "plot_income_average.png")
    plt.show()

if __name__ == "__main__":
    print("グラフを描画しています...")
    plot_macro_trends()
    plot_wealth_distribution()
    plot_apc_trends()
    plot_firm_sales_trends()
    plot_inventory_trends() # 新規追加
    plot_price_trends() # 新規追加
    plot_income_trends()
