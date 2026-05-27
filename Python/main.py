### 各ディレクトリ（Colab環境に合わせて変更してください）
d0 = "./"

import random
import csv

# --- 企業数の設定パラメーター ---
num_total_firms = 10
gov_target_firm_ratio = 0.5

hierarchy_levels = 3
subordinates = 4

living_cost_adult = 100
living_cost_child = 50
living_cost_age = 18

luxury_percent = 20

days_permonth = 30
total_months = 12
total_steps = total_months * days_permonth

# ==========================================
# 整数計算維持のためのスケールアップ
# ==========================================
PRICE_UNIT = 100

monthly_tax = 10 * PRICE_UNIT
gov_spending = 50000 * PRICE_UNIT
initial_money_per_person = 1000 * PRICE_UNIT

production_efficiency_basic = 5000   
production_efficiency_luxury = 2000  

# --- 1. 基底クラスと複式簿記ロジック ---
class BalanceSheet:
    def __init__(self):
        self.assets: int = 0
        self.liabilities: int = 0
        self.equity: int = 0
        self.revenues: int = 0
        self.expenses: int = 0
    @property
    def net_worth(self) -> int: return self.equity + self.revenues - self.expenses
    def is_balanced(self) -> bool: return self.assets == (self.liabilities + self.net_worth)
    def add_cash(self, amount: int): self.assets += amount
    def record_revenue(self, amount: int): self.revenues += amount
    def record_expense(self, amount: int): self.expenses += amount

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
        cls.total_C_basic = 0; cls.total_C_luxury = 0; cls.total_G = 0; 
        cls.total_I = 0; cls.total_T = 0; cls.total_S = 0

    @classmethod
    def get_gdp_components(cls):
        return cls.total_C_basic, cls.total_C_luxury, cls.total_G, cls.total_I, cls.total_T, cls.total_S

    @staticmethod
    def transfer(payer: Agent, payee: Agent, amount: int, category: str = "TRANSFER"):
        if amount <= 0: return
        payer.balance_sheet.add_cash(-amount)
        payer.balance_sheet.record_expense(amount)
        payee.balance_sheet.add_cash(amount)
        payee.balance_sheet.record_revenue(amount)
        assert payer.balance_sheet.is_balanced()
        assert payee.balance_sheet.is_balanced()

        if category == "C_BASIC": Transaction.total_C_basic += amount
        elif category == "C_LUXURY": Transaction.total_C_luxury += amount
        elif category == "G": Transaction.total_G += amount
        elif category == "I": Transaction.total_I += amount
        elif category == "T": Transaction.total_T += amount
        elif category == "S": Transaction.total_S += amount

# --- 2. 個人のデータクラス ---
class Individual:
    def __init__(self, individual_id: int, age: int):
        self.id = individual_id
        self.age = age
        self.daily_living_vol = living_cost_adult if age >= living_cost_age else living_cost_child

# --- 3. エージェントのサブクラス ---
class Household(Agent):
    def __init__(self, name: str, individuals: list[Individual]):
        super().__init__(name)
        self.members = individuals
        
        self.basic_need_vol = sum(ind.daily_living_vol for ind in self.members)
        self.luxury_propensity_percent = luxury_percent 
        
        self.monthly_consumption_money = 0
        self.monthly_income = 0
        self.previous_income = 0 
        self.monthly_consumed_vol_basic = 0
        self.daily_luxury_budget = 0

    def update_monthly_budget(self, current_min_price_basic: int):
        expected_basic_needs_money = self.basic_need_vol * days_permonth * current_min_price_basic
        if self.previous_income > expected_basic_needs_money:
            leftover = self.previous_income - expected_basic_needs_money
            total_luxury_budget = (leftover * self.luxury_propensity_percent) // 100
            self.daily_luxury_budget = total_luxury_budget // days_permonth
        else:
            self.daily_luxury_budget = 0

    def consume(self, firms_C: list['Firm']):
        budget = self.balance_sheet.assets
        
        # --- 1. 必需品の消費（真・Ver 1.2: 在庫ありの中で最安値をランダムに選ぶ） ---
        available_basic_firms = [f for f in firms_C if f.inventory_basic > 0]
        
        if available_basic_firms:
            # 1-1. 在庫がある企業の中から最安値を見つける
            min_price_basic = min(f.price_basic for f in available_basic_firms)
            # 1-2. 最安値の企業のリストを作る
            cheapest_basic_firms = [f for f in available_basic_firms if f.price_basic == min_price_basic]
            # 1-3. その中から完全にランダムに1社を選ぶ（企業1への集中バグを解消）
            target_firm_basic = random.choice(cheapest_basic_firms)
            
            affordable_vol = budget // min_price_basic
            buy_vol = min(self.basic_need_vol, affordable_vol, target_firm_basic.inventory_basic)
            
            if buy_vol > 0:
                spend = buy_vol * min_price_basic
                target_firm_basic.inventory_basic -= buy_vol
                Transaction.transfer(payer=self, payee=target_firm_basic, amount=spend, category="C_BASIC")
                
                budget -= spend
                self.monthly_consumed_vol_basic += buy_vol
                self.monthly_consumption_money += spend

        # --- 2. 嗜好品の消費 ---
        budget_for_luxury = min(budget, self.daily_luxury_budget)
        available_luxury_firms = [f for f in firms_C if f.inventory_luxury > 0]
        
        if available_luxury_firms and budget_for_luxury > 0:
            min_price_luxury = min(f.price_luxury for f in available_luxury_firms)
            cheapest_luxury_firms = [f for f in available_luxury_firms if f.price_luxury == min_price_luxury]
            target_firm_luxury = random.choice(cheapest_luxury_firms)
            
            affordable_vol = budget_for_luxury // min_price_luxury
            buy_vol = min(affordable_vol, target_firm_luxury.inventory_luxury)
            
            if buy_vol > 0:
                spend = buy_vol * min_price_luxury
                target_firm_luxury.inventory_luxury -= buy_vol
                Transaction.transfer(payer=self, payee=target_firm_luxury, amount=spend, category="C_LUXURY")
                self.monthly_consumption_money += spend

    def pay_tax(self, gov: 'Government', tax_amount: int):
        amount = min(self.balance_sheet.assets, tax_amount)
        if amount > 0:
            Transaction.transfer(payer=self, payee=gov, amount=amount, category="T")

class Firm(Agent):
    def __init__(self, name: str, is_target_C: bool = False, is_target_G: bool = False):
        super().__init__(name)
        self.is_target_C = is_target_C
        self.is_target_G = is_target_G
        self.employees = []
        
        self.previous_revenues = 0
        self.monthly_revenue = 0
        self.inventory_basic = 0
        self.inventory_luxury = 0
        self.price_basic = PRICE_UNIT
        self.price_luxury = PRICE_UNIT

    def produce_goods(self):
        total_weight = sum(emp["weight"] for emp in self.employees)
        self.inventory_basic += total_weight * production_efficiency_basic
        self.inventory_luxury += total_weight * production_efficiency_luxury

    def adjust_prices(self):
        # 必需品の価格調整
        if self.inventory_basic > 0:
            reduction = max(1, (self.price_basic * 5) // 100)
            self.price_basic = max(1, self.price_basic - reduction)
        else:
            increase = max(1, (self.price_basic * 5) // 100)
            self.price_basic += increase

        # 嗜好品の価格調整
        if self.inventory_luxury > 0:
            reduction = max(1, (self.price_luxury * 5) // 100)
            self.price_luxury = max(1, self.price_luxury - reduction)
        else:
            increase = max(1, (self.price_luxury * 5) // 100)
            self.price_luxury += increase

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
        if is_G: firms_G.append(firm)
    
    all_households = [] 
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
                
    for firm in all_firms:
        firm.produce_goods()

    for hh in all_households:
        initial_money = len(hh.members) * initial_money_per_person
        Transaction.transfer(payer=gov, payee=hh, amount=initial_money, category="INITIAL_MONEY")
        hh.monthly_income += initial_money
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
        if step % 30 == 1:
            # 在庫がある企業の中での最安値を予算基準とする（在庫切れなら100と仮定）
            available_for_budget = [f for f in firms_C if f.inventory_basic > 0]
            current_min_price = min(f.price_basic for f in available_for_budget) if available_for_budget else PRICE_UNIT
            for hh in all_households:
                hh.update_monthly_budget(current_min_price)

        # 毎ステップ、家計の行動順序をランダムにシャッフルする
        random.shuffle(all_households)

        # 毎日: 消費
        for hh in all_households:
            hh.consume(firms_C)
            
        if step % 30 == 0:
            month = step // 30
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

            # 企業の処理（売上計算、価格改定、在庫補充）
            for firm in all_firms:
                firm.calculate_monthly_revenue()
                
                firm_sales_data.append({
                    "Month": month, 
                    "Firm_ID": firm.name, 
                    "Revenue": firm.monthly_revenue, 
                    "Inventory_Basic": firm.inventory_basic,
                    "Inventory_Luxury": firm.inventory_luxury,
                    "Price_Basic": firm.price_basic,   
                    "Price_Luxury": firm.price_luxury, 
                    "Is_G_Target": firm.is_target_G
                })
                firm.adjust_prices()
                firm.produce_goods()

            # 家計のログ
            for hh in all_households:
                level = hh.name.split("_")[-1].replace("階層", "")
                apc = (hh.monthly_consumption_money / hh.monthly_income) if hh.monthly_income > 0 else 0.0
                
                apc_data.append({
                    "Month": month, 
                    "Household_ID": hh.name, 
                    "Hierarchy_Level": level,
                    "Income": hh.monthly_income, 
                    "Consumption_Money": hh.monthly_consumption_money, 
                    "Consumed_Volume_Basic": hh.monthly_consumed_vol_basic, 
                    "APC": apc
                })
                hh.previous_income = hh.monthly_income 
                hh.monthly_consumption_money = 0
                hh.monthly_income = 0
                hh.monthly_consumed_vol_basic = 0

    print("=== シミュレーション完了 ===")
    
    # === ファイル出力名をすべて _v1.2.csv に戻す ===
    with open(d0 + "age01_macro_data_v1.2.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Month", "C_Basic", "C_Luxury", "C_Total", "G", "I", "T", "S", "GDP", "Gov_Deficit"])
        writer.writeheader()
        writer.writerows(macro_data)
        
    with open(d0 + "age01_wealth_distribution_v1.2.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Household_ID", "Hierarchy_Level", "Final_Assets"])
        for hh in all_households:
            level = hh.name.split("_")[-1].replace("階層", "")
            writer.writerow([hh.name, level, hh.balance_sheet.assets])

    with open(d0 + "age01_apc_data_v1.2.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Month", "Household_ID", "Hierarchy_Level", "Income", "Consumption_Money", "Consumed_Volume_Basic", "APC"])
        writer.writeheader()
        writer.writerows(apc_data)

    with open(d0 + "age01_firm_sales_data_v1.2.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Month", "Firm_ID", "Revenue", "Inventory_Basic", "Inventory_Luxury", "Price_Basic", "Price_Luxury", "Is_G_Target"])
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