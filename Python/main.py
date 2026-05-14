### 各ディレクトリ
d0 = "./"

import random
import csv

# --- 企業数の設定パラメーター ---
num_total_firms = 10
gov_target_firm_ratio = 0.5  # 政府事業を受注する企業の割合 (0.0 〜 1.0)

# --- 企業数の従業員構成 ---
hierarchy_levels = 3
subordinates = 4

# -- 個人の生活費（大人と子ども） --
living_cost_adult = 100
living_cost_child = 50
living_cost_age = 18

# -- 家計が嗜好品に支払う、収入額の割合 --
luxury_percent = 20

# -- 計算ステップ --
days_permonth = 30
total_months = 12
total_steps = total_months * days_permonth

# -- 政府 --
monthly_tax = 10        # 毎月の、1家計あたりの税金
gov_spending = 50000    # 毎月の、政府が企業に支払う事業対価

initial_money_per_person = 1000 # 計算の初めに、政府が家計に配る金額。

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
    total_C_basic: int = 0
    total_C_luxury: int = 0
    total_G: int = 0
    total_I: int = 0
    total_T: int = 0
    total_S: int = 0

    @classmethod
    def reset_statistics(cls):
        cls.total_C_basic = 0
        cls.total_C_luxury = 0
        cls.total_G = 0
        cls.total_I = 0
        cls.total_T = 0
        cls.total_S = 0

    @classmethod
    def get_gdp_components(cls) -> tuple[int, int, int, int, int, int]:
        return cls.total_C_basic, cls.total_C_luxury, cls.total_G, cls.total_I, cls.total_T, cls.total_S

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

        if category == "C_BASIC":
            Transaction.total_C_basic += amount
        elif category == "C_LUXURY":
            Transaction.total_C_luxury += amount
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
        
        self.basic_need_cap = sum(ind.daily_living_cost for ind in self.members)
        self.luxury_propensity_percent = luxury_percent
        
        self.monthly_consumption = 0
        self.monthly_income = 0
        self.previous_income = 0 # --- 新規追加: 前月の収入を記録する変数 ---
        self.daily_luxury_budget = 0

    def update_monthly_budget(self):
        """月初めに、前月の収入（フロー）から今月の嗜好品予算を計算する"""
        expected_basic_needs = self.basic_need_cap * days_permonth
        
        # --- 変更点: 所持金(ストック)ではなく、前月収入(フロー)を基準にする ---
        if self.previous_income > expected_basic_needs:
            # 収入のうち、予想生活費を引いた余剰資金
            leftover = self.previous_income - expected_basic_needs
            # 余剰資金の20%を今月の嗜好品総予算とする
            total_luxury_budget = (leftover * self.luxury_propensity_percent) // 100
            # 1日あたりに日割り
            self.daily_luxury_budget = total_luxury_budget // days_permonth
        else:
            self.daily_luxury_budget = 0

    def consume(self, firms_C: list['Firm']):
        budget = self.balance_sheet.assets
        spend_basic = min(budget, self.basic_need_cap)
        current_leftover = budget - spend_basic
        spend_luxury = min(current_leftover, self.daily_luxury_budget)

        self.monthly_consumption += (spend_basic + spend_luxury)

        if spend_basic > 0:
            target_firm = random.choice(firms_C)
            Transaction.transfer(payer=self, payee=target_firm, amount=spend_basic, category="C_BASIC")
            
        if spend_luxury > 0:
            target_firm = random.choice(firms_C)
            Transaction.transfer(payer=self, payee=target_firm, amount=spend_luxury, category="C_LUXURY")

    def pay_tax(self, gov: 'Government', tax_amount: int):
        amount = min(self.balance_sheet.assets, tax_amount)
        if amount > 0:
            Transaction.transfer(payer=self, payee=gov, amount=amount, category="T")

    def pay_save(self, target_bank: 'Bank', save_amount: int):
        amount = min(self.balance_sheet.assets, save_amount)
        if amount > 0:
            Transaction.transfer(payer=self, payee=target_bank, amount=amount, category="S")


class Firm(Agent):
    def __init__(self, name: str, is_target_C: bool = False, is_target_G: bool = False):
        super().__init__(name)
        self.is_target_C = is_target_C
        self.is_target_G = is_target_G
        self.employees = []
        
        self.previous_revenues = 0
        self.monthly_revenue = 0

    def calculate_monthly_revenue(self):
        self.monthly_revenue = self.balance_sheet.revenues - self.previous_revenues
        self.previous_revenues = self.balance_sheet.revenues

    def add_employee(self, household: Household, weight: int):
        self.employees.append({"household": household, "weight": weight})

    def pay_salary(self):
        total_payroll = self.balance_sheet.assets
        if total_payroll <= 0: return
        total_weight = sum(emp["weight"] for emp in self.employees)
        if total_weight == 0: return

        for emp in self.employees:
            amount = (total_payroll * emp["weight"]) // total_weight
            if amount > 0:
                Transaction.transfer(payer=self, payee=emp["household"], amount=amount, category="SALARY")
                emp["household"].monthly_income += amount


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
    
    all_firms = []
    firms_C = []
    firms_G = []
    
    num_G_firms = max(1, int(num_total_firms * gov_target_firm_ratio))
    
    for i in range(1, num_total_firms + 1):
        is_G = (i <= num_G_firms)
        name = f"企業_{i}" + ("(G・C対象)" if is_G else "(C対象)")
        
        firm = Firm(name, is_target_C=True, is_target_G=is_G)
        all_firms.append(firm)
        firms_C.append(firm)
        if is_G:
            firms_G.append(firm)
        
    all_households = [] # --- 修正: 抜け漏れを追加 ---
    household_id_counter = 1
    individual_id_counter = 1
    
    for firm in all_firms:
        for level in range(hierarchy_levels):
            num_people_in_level = subordinates ** level
            weight_per_person = subordinates ** (hierarchy_levels - 1 - level)
            
            for _ in range(num_people_in_level):
                adult = Individual(individual_id_counter, age=30)
                child = Individual(individual_id_counter + 1, age=10)
                individual_id_counter += 2
                hh = Household(f"家計_{household_id_counter}_階層{level}", [adult, child])
                household_id_counter += 1
                
                firm.add_employee(hh, weight_per_person)
                all_households.append(hh)
                
    for hh in all_households:
        initial_money = len(hh.members) * initial_money_per_person
        Transaction.transfer(payer=gov, payee=hh, amount=initial_money, category="INITIAL_MONEY")
        hh.monthly_income += initial_money
        # --- 追加: 初期配布金（給付金）を1ヶ月目の収入ベースとする ---
        hh.previous_income = initial_money 
        
    return gov, bank, all_firms, firms_C, firms_G, all_households


def run_simulation():
    gov, bank, all_firms, firms_C, firms_G, all_households = setup_simulation()
        
    macro_data = []
    apc_data = []
    firm_sales_data = []

    print("=== シミュレーション開始 ===")
    Transaction.reset_statistics()
    
    for step in range(1, total_steps + 1):
        if step % days_permonth == 1:
            for hh in all_households:
                hh.update_monthly_budget()

        for hh in all_households:
            hh.consume(firms_C)
            
        if step % days_permonth == 0:
            month = step // days_permonth
            print(f"--- 第{month}ヶ月目 処理実行 ---")
            
            for firm in all_firms: firm.pay_salary()
            for hh in all_households: hh.pay_tax(gov, monthly_tax)
            
            if len(firms_G) > 0:
                spending_per_firm = gov_spending // len(firms_G)
                for firm in firms_G:
                    gov.pay_firm(firm, spending_per_firm)
            
            c_b, c_l, g, i, t, s = Transaction.get_gdp_components()
            total_c = c_b + c_l
            
            macro_data.append({
                "Month": month, "C_Basic": c_b, "C_Luxury": c_l, "C_Total": total_c,
                "G": g, "I": i, "T": t, "S": s, "GDP": total_c + g + i,
                "Gov_Deficit": -gov.balance_sheet.assets
            })
            
            Transaction.reset_statistics()

            # 企業の売上高の記録
            for firm in all_firms:
                firm.calculate_monthly_revenue()
                firm_sales_data.append({
                    "Month": month,
                    "Firm_ID": firm.name,
                    "Revenue": firm.monthly_revenue,
                    "Is_G_Target": firm.is_target_G
                })

            # 家計のAPCを記録
            for hh in all_households:
                level = hh.name.split("_")[-1].replace("階層", "")
                apc = (hh.monthly_consumption / hh.monthly_income) if hh.monthly_income > 0 else 0.0
                
                apc_data.append({
                    "Month": month,
                    "Household_ID": hh.name,
                    "Hierarchy_Level": level,
                    "Income": hh.monthly_income,
                    "Consumption": hh.monthly_consumption,
                    "APC": apc
                })
                # --- 追加: 来月の予算計算のために今月の収入を保存 ---
                hh.previous_income = hh.monthly_income 
                
                hh.monthly_consumption = 0
                hh.monthly_income = 0

    print("=== シミュレーション完了 ===")
    
    with open(d0 + "age01_macro_data_v1.1.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Month", "C_Basic", "C_Luxury", "C_Total", "G", "I", "T", "S", "GDP", "Gov_Deficit"])
        writer.writeheader()
        writer.writerows(macro_data)
        
    with open(d0 + "age01_wealth_distribution_v1.1.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Household_ID", "Hierarchy_Level", "Final_Assets"])
        for hh in all_households:
            level = hh.name.split("_")[-1].replace("階層", "")
            writer.writerow([hh.name, level, hh.balance_sheet.assets])

    with open(d0 + "age01_apc_data_v1.1.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Month", "Household_ID", "Hierarchy_Level", "Income", "Consumption", "APC"])
        writer.writeheader()
        writer.writerows(apc_data)

    with open(d0 + "age01_firm_sales_data.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Month", "Firm_ID", "Revenue", "Is_G_Target"])
        writer.writeheader()
        writer.writerows(firm_sales_data)

    print(f">> {d0} にCSVファイルを出力しました。")

    print("\n【結果確認】")
    firms_assets = sum(f.balance_sheet.assets for f in all_firms)
    hh_assets = sum(h.balance_sheet.assets for h in all_households)
    total_assets = gov.balance_sheet.assets + bank.balance_sheet.assets + firms_assets + hh_assets
    print(f"全企業の資産（端数留保含む）: {firms_assets}")
    print(f"系全体の総資産: {total_assets}")  # 常に0になるはず

if __name__ == "__main__":
    run_simulation()