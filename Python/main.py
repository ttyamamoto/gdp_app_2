### 各ディレクトリ
d0 = "./"

import random
import csv

living_cost_adult = 100
living_cost_child = 50
living_cost_age = 18

total_steps = 360 # 12ヶ月に延長
monthly_tax = 10
gov_spending = 50000

initial_money_per_person = 1000

# --- 1. 基底クラスと複式簿記ロジック ---
class BalanceSheet:
    def __init__(self):
        self.assets: int = 0
        self.liabilities: int = 0
        self.equity: int = 0
        self.revenues: int = 0
        self.expenses: int = 0

    @property
    def net_worth(self) -> int:
        return self.equity + self.revenues - self.expenses

    def is_balanced(self) -> bool:
        return self.assets == (self.liabilities + self.net_worth)

    def add_cash(self, amount: int):
        self.assets += amount

    def record_revenue(self, amount: int):
        self.revenues += amount

    def record_expense(self, amount: int):
        self.expenses += amount


class Agent:
    def __init__(self, name: str):
        self.name = name
        self.balance_sheet = BalanceSheet()


class Transaction:
    total_C: int = 0
    total_G: int = 0
    total_I: int = 0
    total_T: int = 0
    total_S: int = 0

    @classmethod
    def reset_statistics(cls):
        """月次ごとのフローを計測するために統計をリセットする"""
        cls.total_C = 0
        cls.total_G = 0
        cls.total_I = 0
        cls.total_T = 0
        cls.total_S = 0

    @classmethod
    def get_gdp_components(cls) -> tuple[int, int, int]:
        """C, G, I の成分を個別に返す（分析用）"""
        return cls.total_C, cls.total_G, cls.total_I, cls.total_T, cls.total_S

    @staticmethod
    def transfer(payer: Agent, payee: Agent, amount: int, category: str = "TRANSFER"):
        if amount <= 0:
            return

        payer.balance_sheet.add_cash(-amount)
        payer.balance_sheet.record_expense(amount)

        payee.balance_sheet.add_cash(amount)
        payee.balance_sheet.record_revenue(amount)

        assert payer.balance_sheet.is_balanced(), f"{payer.name}のB/Sが崩壊しました！"
        assert payee.balance_sheet.is_balanced(), f"{payee.name}のB/Sが崩壊しました！"

        if category == "C":
            Transaction.total_C += amount
        elif category == "G":
            Transaction.total_G += amount
        elif category == "I":
            Transaction.total_I += amount
        elif category == "T":
            Transaction.total_T += amount
        elif category == "S":
            Transaction.total_S += amount

# --- 2. 個人のデータクラス ---
class Individual:
    def __init__(self, individual_id: int, age: int):
        self.id = individual_id
        self.age = age
        self.daily_living_cost = living_cost_adult if age >= living_cost_age else living_cost_child

# --- 3. エージェントのサブクラス ---
class Household(Agent):
    def __init__(self, name: str, individuals: list[Individual]):
        super().__init__(name)
        self.members = individuals
        self.daily_expense_cap = sum(ind.daily_living_cost for ind in self.members)

    def consume(self, target_firm: 'Firm'):
        budget = self.balance_sheet.assets
        actual_spending = min(budget, self.daily_expense_cap)
        if actual_spending > 0:
            Transaction.transfer(payer=self, payee=target_firm, amount=actual_spending, category="C")

    def pay_tax(self, gov: 'Government', tax_amount: int):
        amount = min(self.balance_sheet.assets, tax_amount)
        if amount > 0:
            Transaction.transfer(payer=self, payee=gov, amount=amount, category="T")

    def pay_save(self, target_bank: 'Bank', tax_amount: int):
        amount = min(self.balance_sheet.assets, tax_amount)
        if amount > 0:
            Transaction.transfer(payer=self, payee=target_bank, amount=amount, category="S")


class Firm(Agent):
    def __init__(self, name: str, is_target_C: bool = False, is_target_G: bool = False):
        super().__init__(name)
        self.is_target_C = is_target_C
        self.is_target_G = is_target_G
        self.employees = []

    def add_employee(self, household: Household, salary_ratio: float):
        self.employees.append({"household": household, "ratio": salary_ratio})

    def pay_salary(self):
        total_payroll = self.balance_sheet.assets
        if total_payroll <= 0:
            return
        for emp in self.employees:
            amount = int(total_payroll * emp["ratio"])
            if amount > 0:
                Transaction.transfer(payer=self, payee=emp["household"], amount=amount, category="SALARY")


class Government(Agent):
    def __init__(self, name: str):
        super().__init__(name)

    def pay_firm(self, target_firm: Firm, amount: int):
        Transaction.transfer(payer=self, payee=target_firm, amount=amount, category="G")


class Bank(Agent):
    def __init__(self, name: str):
        super().__init__(name)

    def pay_firm(self, target_firm: Firm, amount: int):
        Transaction.transfer(payer=self, payee=target_firm, amount=amount, category="I")


# --- 4. メインループとCSV出力 ---
def setup_simulation():
    gov = Government("政府")
    bank = Bank("銀行")
    
    firm_G = Firm("公共事業(G対象)", is_target_G=True)
    firms_C = [Firm(f"消費財メーカー{i}(C対象)", is_target_C=True) for i in range(1, 10)]
    all_firms = [firm_G] + firms_C
    all_households = []
    
    # 全ての企業の階層構造。３階層、1人につき4人の部下。
    hierarchy_levels = 3
    subordinates = 4
    
    household_id_counter = 1
    individual_id_counter = 1
    
    for firm in all_firms:
        for level in range(hierarchy_levels):
            num_people_in_level = subordinates ** level
            # 給与配分率の決定。
            ratio_per_person = (1.0 / hierarchy_levels) / num_people_in_level
            
            # 企業に属する労働者から、家計の構造を与える。（全家計で固定）
            for _ in range(num_people_in_level):
                adult = Individual(individual_id_counter, age=30)
                child = Individual(individual_id_counter + 1, age=10)
                individual_id_counter += 2
                hh = Household(f"家計_{household_id_counter}_階層{level}", [adult, child])
                household_id_counter += 1
                all_households.append(hh)
                firm.add_employee(hh, ratio_per_person)
                
    # 初期値として、政府から家計に資産を与える。
    for hh in all_households:
        initial_money = len(hh.members) * initial_money_per_person
        Transaction.transfer(payer=gov, payee=hh, amount=initial_money, category="INITIAL_MONEY")
        
    return gov, bank, all_firms, firms_C, firm_G, all_households


def run_simulation():
    gov, bank, all_firms, firms_C, firm_G, all_households = setup_simulation()
        
    # ロギング用データの準備
    macro_data = []

    print("=== シミュレーション開始 ===")
    Transaction.reset_statistics()
    
    for step in range(1, total_steps + 1):
        # 毎日: 消費
        for hh in all_households:
            target_firm = random.choice(firms_C)
            hh.consume(target_firm)
            
        # 30日ごと: 月末処理
        if step % 30 == 0:
            month = step // 30
            print(f"--- 第{month}ヶ月目 処理実行 ---")
            
            for firm in all_firms: firm.pay_salary()
            for hh in all_households: hh.pay_tax(gov, monthly_tax)
            gov.pay_firm(firm_G, gov_spending)
            
            # --- データの記録 (GDP統計の取得) ---
            c, g, i, t, s = Transaction.get_gdp_components()
            macro_data.append({
                "Month": month,
                "C": c,
                "G": g,
                "I": i,
                "T": t,
                "S": s,
                "GDP": c + g + i,
                "Gov_Deficit": -gov.balance_sheet.assets # 政府の累積赤字
            })
            
            # 次の月のフロー計測のためにリセット
            Transaction.reset_statistics()

    print("=== シミュレーション完了 ===")
    
    # CSV出力 1: マクロ経済データ (時系列)
    with open(d0 + "age01_macro_data.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Month", "C", "G", "I", "T", "S", "GDP", "Gov_Deficit"])
        writer.writeheader()
        writer.writerows(macro_data)
        
    # CSV出力 2: ミクロ家計データ (シミュレーション終了時の富の分布)
    with open(d0 + "age01_wealth_distribution.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Household_ID", "Hierarchy_Level", "Final_Assets"])
        for hh in all_households:
            # 名前から階層レベルを抽出 (例: "家計_1_階層0" -> 0)
            level = hh.name.split("_")[-1].replace("階層", "")
            writer.writerow([hh.name, level, hh.balance_sheet.assets])

    print(">> macro_data.csv と wealth_distribution.csv を出力しました。")

    # 結果の簡単な確認
    print("\n【結果確認】")
    print(f"政府の最終資産(負債): {gov.balance_sheet.assets}")
    
    # 企業の資産（内部留保）の偏りを確認
    print("G対象企業の資産:", firm_G.balance_sheet.assets)
    print("C対象企業(代表1社)の資産:", firms_C[0].balance_sheet.assets)
    firms_assets = firm_G.balance_sheet.assets
    for firm in firms_C[:]:
        firms_assets += firm.balance_sheet.assets
    print("全企業の資産:", firms_assets)

    # 全家計の資産（内部留保）の偏りを確認
    print("１家計の資産:", all_households[0].balance_sheet.assets)
    hh_assets = all_households[0].balance_sheet.assets
    for hh in all_households[1:]:
        hh_assets += hh.balance_sheet.assets
    print("全家計の資産:", hh_assets)

    # 系の総資産の確認（マクロの保存則）
    total_assets = gov.balance_sheet.assets + bank.balance_sheet.assets + firms_assets + hh_assets
    print(f"系全体の総資産: {total_assets}")  # 常に0になるはず

if __name__ == "__main__":
    # エージェントの生成
    gov = Agent("政府")
    hh = Agent("家計A")

    print("--- 初期配布 (政府から家計へ 100000 単位) ---")
    # 政府が家計に10万渡す（この時、政府は無からお金を刷るので、政府の現金はマイナスになる）
    Transaction.transfer(payer=gov, payee=hh, amount=100000, category="INITIAL_MONEY")
    
    print(f"政府の資産 (Cash): {gov.balance_sheet.assets}")
    print(f"家計の資産 (Cash): {hh.balance_sheet.assets}")
    
    # 系の総資産の確認（マクロの保存則）
    total_assets = gov.balance_sheet.assets + hh.balance_sheet.assets
    print(f"系全体の総資産: {total_assets}")  # 常に0になるはず

if __name__ == "__main__":
    run_simulation()
