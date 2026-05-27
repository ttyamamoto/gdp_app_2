#include <iostream>
#include <vector>
#include <string>
#include <cassert>
#include <fstream>
#include <random>
#include <algorithm>

// ==========================================
// 設定・固定値パラメーター
// ==========================================
const std::string d0 = "./";

const int num_total_firms = 10;
const double gov_target_firm_ratio = 0.5;

const int hierarchy_levels = 3;
const int subordinates = 4;

const long long living_cost_adult = 100;
const long long living_cost_child = 50;
const int living_cost_age = 18;

const long long luxury_percent = 20;

const int days_permonth = 30;
const int total_months = 12;
const int total_steps = total_months * days_permonth;

// --- 整数計算維持のためのスケールアップ ---
const long long PRICE_UNIT = 100;

const long long monthly_tax = 10 * PRICE_UNIT;
const long long gov_spending = 50000 * PRICE_UNIT;
const long long initial_money_per_person = 1000 * PRICE_UNIT;

const long long production_efficiency_basic = 5000;
const long long production_efficiency_luxury = 2000;

// ==========================================
// 1. 基底クラスと複式簿記ロジック
// ==========================================
class BalanceSheet {
public:
    long long assets = 0;
    long long liabilities = 0;
    long long equity = 0;
    long long revenues = 0;
    long long expenses = 0;

    long long get_net_worth() const { return equity + revenues - expenses; }
    bool is_balanced() const { return assets == (liabilities + get_net_worth()); }
    void add_cash(long long amount) { assets += amount; }
    void record_revenue(long long amount) { revenues += amount; }
    void record_expense(long long amount) { expenses += amount; }
};

class Agent {
public:
    std::string name;
    BalanceSheet balance_sheet;
    Agent(std::string n) : name(n) {}
    virtual ~Agent() = default;
};

class Transaction {
public:
    static long long total_C_basic, total_C_luxury, total_G, total_I, total_T, total_S;
    static void reset_statistics() {
        total_C_basic = 0; total_C_luxury = 0; total_G = 0;
        total_I = 0; total_T = 0; total_S = 0;
    }
    static void transfer(Agent* payer, Agent* payee, long long amount, std::string category = "TRANSFER") {
        if (amount <= 0) return;
        payer->balance_sheet.add_cash(-amount);
        payer->balance_sheet.record_expense(amount);
        payee->balance_sheet.add_cash(amount);
        payee->balance_sheet.record_revenue(amount);
        assert(payer->balance_sheet.is_balanced() && "Payer B/S broken!");
        assert(payee->balance_sheet.is_balanced() && "Payee B/S broken!");

        if (category == "C_BASIC") total_C_basic += amount;
        else if (category == "C_LUXURY") total_C_luxury += amount;
        else if (category == "G") total_G += amount;
        else if (category == "I") total_I += amount;
        else if (category == "T") total_T += amount;
        else if (category == "S") total_S += amount;
    }
};

long long Transaction::total_C_basic = 0;
long long Transaction::total_C_luxury = 0;
long long Transaction::total_G = 0;
long long Transaction::total_I = 0;
long long Transaction::total_T = 0;
long long Transaction::total_S = 0;

// ==========================================
// 2. 個人のデータクラス
// ==========================================
class Individual {
public:
    int id;
    int age;
    long long daily_living_vol;
    Individual(int id, int age) : id(id), age(age) {
        daily_living_vol = (age >= living_cost_age) ? living_cost_adult : living_cost_child;
    }
};

class Firm;
class Government;
class Bank;

// ==========================================
// 3. エージェントのサブクラス
// ==========================================
class Household : public Agent {
public:
    std::vector<Individual> members;
    long long basic_need_vol;
    int hierarchy_level;

    long long monthly_consumption_money = 0;
    long long monthly_income = 0;
    long long previous_income = 0;
    long long monthly_consumed_vol_basic = 0;
    long long daily_luxury_budget = 0;

    Household(std::string n, const std::vector<Individual>& inds, int level) 
        : Agent(n), members(inds), hierarchy_level(level) {
        basic_need_vol = 0;
        for (const auto& ind : members) basic_need_vol += ind.daily_living_vol;
    }

    void update_monthly_budget(long long current_min_price_basic) {
        long long expected_basic_needs_money = basic_need_vol * days_permonth * current_min_price_basic;
        if (previous_income > expected_basic_needs_money) {
            long long leftover = previous_income - expected_basic_needs_money;
            long long total_luxury_budget = (leftover * luxury_percent) / 100;
            daily_luxury_budget = total_luxury_budget / days_permonth;
        } else {
            daily_luxury_budget = 0;
        }
    }

    void consume(const std::vector<Firm*>& firms_C, std::mt19937& gen);
    void pay_tax(Government* gov, long long tax_amount);
};

class Firm : public Agent {
public:
    bool is_target_C;
    bool is_target_G;
    
    long long previous_revenues = 0;
    long long monthly_revenue = 0;
    long long inventory_basic = 0;
    long long inventory_luxury = 0;
    long long price_basic = PRICE_UNIT;
    long long price_luxury = PRICE_UNIT;

    struct EmployeeRecord { Household* household; long long weight; };
    std::vector<EmployeeRecord> employees;

    Firm(std::string n, bool c_target = false, bool g_target = false) 
        : Agent(n), is_target_C(c_target), is_target_G(g_target) {}

    void produce_goods() {
        long long total_weight = 0;
        for (const auto& emp : employees) total_weight += emp.weight;
        inventory_basic += total_weight * production_efficiency_basic;
        inventory_luxury += total_weight * production_efficiency_luxury;
    }

    void adjust_prices() {
        if (inventory_basic > 0) {
            long long reduction = std::max(1LL, (price_basic * 5) / 100);
            price_basic = std::max(1LL, price_basic - reduction);
        } else {
            long long increase = std::max(1LL, (price_basic * 5) / 100);
            price_basic += increase;
        }

        if (inventory_luxury > 0) {
            long long reduction = std::max(1LL, (price_luxury * 5) / 100);
            price_luxury = std::max(1LL, price_luxury - reduction);
        } else {
            long long increase = std::max(1LL, (price_luxury * 5) / 100);
            price_luxury += increase;
        }
    }

    void calculate_monthly_revenue() {
        monthly_revenue = balance_sheet.revenues - previous_revenues;
        previous_revenues = balance_sheet.revenues;
    }

    void add_employee(Household* hh, long long weight) {
        employees.push_back({hh, weight});
    }

    void pay_salary() {
        long long total_payroll = balance_sheet.assets;
        if (total_payroll <= 0) return;
        long long total_weight = 0;
        for (const auto& emp : employees) total_weight += emp.weight;
        if (total_weight == 0) return;

        for (const auto& emp : employees) {
            long long amount = (total_payroll * emp.weight) / total_weight;
            if (amount > 0) {
                Transaction::transfer(this, emp.household, amount, "SALARY");
                emp.household->monthly_income += amount;
            }
        }
    }
};

class Government : public Agent {
public:
    Government(std::string n) : Agent(n) {}
    void pay_firm(Firm* target_firm, long long amount) {
        Transaction::transfer(this, target_firm, amount, "G");
    }
};

class Bank : public Agent {
public:
    Bank(std::string n) : Agent(n) {}
};

// ==========================================
// メソッドの実装
// ==========================================
void Household::consume(const std::vector<Firm*>& firms_C, std::mt19937& gen) {
    long long budget = balance_sheet.assets;

    // 1. 必需品の消費 (Ver 1.2: 在庫ありの中で最安値をランダムに選ぶ)
    std::vector<Firm*> available_basic;
    for (auto* f : firms_C) {
        if (f->inventory_basic > 0) available_basic.push_back(f);
    }

    if (!available_basic.empty()) {
        long long min_price = available_basic[0]->price_basic;
        for (auto* f : available_basic) {
            if (f->price_basic < min_price) min_price = f->price_basic;
        }

        std::vector<Firm*> cheapest_firms;
        for (auto* f : available_basic) {
            if (f->price_basic == min_price) cheapest_firms.push_back(f);
        }

        std::uniform_int_distribution<> dis(0, cheapest_firms.size() - 1);
        Firm* target = cheapest_firms[dis(gen)];

        long long affordable_vol = budget / min_price;
        long long buy_vol = std::min({basic_need_vol, affordable_vol, target->inventory_basic});

        if (buy_vol > 0) {
            long long spend = buy_vol * min_price;
            target->inventory_basic -= buy_vol;
            Transaction::transfer(this, target, spend, "C_BASIC");
            budget -= spend;
            monthly_consumed_vol_basic += buy_vol;
            monthly_consumption_money += spend;
        }
    }

    // 2. 嗜好品の消費
    long long budget_for_luxury = std::min(budget, daily_luxury_budget);
    std::vector<Firm*> available_luxury;
    for (auto* f : firms_C) {
        if (f->inventory_luxury > 0) available_luxury.push_back(f);
    }

    if (!available_luxury.empty() && budget_for_luxury > 0) {
        long long min_price = available_luxury[0]->price_luxury;
        for (auto* f : available_luxury) {
            if (f->price_luxury < min_price) min_price = f->price_luxury;
        }

        std::vector<Firm*> cheapest_firms;
        for (auto* f : available_luxury) {
            if (f->price_luxury == min_price) cheapest_firms.push_back(f);
        }

        std::uniform_int_distribution<> dis(0, cheapest_firms.size() - 1);
        Firm* target = cheapest_firms[dis(gen)];

        long long affordable_vol = budget_for_luxury / min_price;
        long long buy_vol = std::min(affordable_vol, target->inventory_luxury);

        if (buy_vol > 0) {
            long long spend = buy_vol * min_price;
            target->inventory_luxury -= buy_vol;
            Transaction::transfer(this, target, spend, "C_LUXURY");
            monthly_consumption_money += spend;
        }
    }
}

void Household::pay_tax(Government* gov, long long tax_amount) {
    long long amount = std::min(balance_sheet.assets, tax_amount);
    if (amount > 0) Transaction::transfer(this, gov, amount, "T");
}

// ==========================================
// 4. メインループとCSV出力
// ==========================================
int main() {
    std::random_device rd;
    std::mt19937 gen(rd());

    Government gov("政府");
    Bank bank("銀行");

    std::vector<Firm> all_firms_instances;
    all_firms_instances.reserve(num_total_firms); 

    int num_G_firms = std::max(1, (int)(num_total_firms * gov_target_firm_ratio));

    for (int i = 1; i <= num_total_firms; ++i) {
        bool is_G = (i <= num_G_firms);
        all_firms_instances.emplace_back("企業_" + std::to_string(i) + (is_G ? "(G・C対象)" : "(C対象)"), true, is_G);
    }

    std::vector<Firm*> all_firms, firms_C, firms_G;
    for (auto& firm : all_firms_instances) {
        all_firms.push_back(&firm);
        firms_C.push_back(&firm);
        if (firm.is_target_G) firms_G.push_back(&firm);
    }

    int total_households_count = 0;
    for (int level = 0; level < hierarchy_levels; ++level) {
        total_households_count += std::pow(subordinates, level);
    }
    total_households_count *= num_total_firms;

    std::vector<Household> all_households;
    all_households.reserve(total_households_count);

    int household_id_counter = 1;
    int individual_id_counter = 1;

    for (auto* firm : all_firms) {
        for (int level = 0; level < hierarchy_levels; ++level) {
            int num_people_in_level = std::pow(subordinates, level);
            long long weight_per_person = std::pow(subordinates, hierarchy_levels - 1 - level);

            for (int p = 0; p < num_people_in_level; ++p) {
                Individual adult(individual_id_counter++, 30);
                Individual child(individual_id_counter++, 10);
                all_households.emplace_back("家計_" + std::to_string(household_id_counter++) + "_階層" + std::to_string(level), std::vector<Individual>{adult, child}, level);
                firm->add_employee(&all_households.back(), weight_per_person);
            }
        }
    }

    for (auto* firm : all_firms) firm->produce_goods();

    for (auto& hh : all_households) {
        long long initial_money = hh.members.size() * initial_money_per_person;
        Transaction::transfer(&gov, &hh, initial_money, "INITIAL_MONEY");
        hh.monthly_income += initial_money;
        hh.previous_income = initial_money;
    }

    std::ofstream macro_csv(d0 + "age01_macro_data_v1.2.csv");
    macro_csv << "Month,C_Basic,C_Luxury,C_Total,G,I,T,S,GDP,Gov_Deficit\n";

    std::ofstream apc_csv(d0 + "age01_apc_data_v1.2.csv");
    apc_csv << "Month,Household_ID,Hierarchy_Level,Income,Consumption_Money,Consumed_Volume_Basic,APC\n";

    std::ofstream sales_csv(d0 + "age01_firm_sales_data_v1.2.csv");
    sales_csv << "Month,Firm_ID,Revenue,Inventory_Basic,Inventory_Luxury,Price_Basic,Price_Luxury,Is_G_Target\n";

    std::cout << "=== シミュレーション開始 ===\n";
    Transaction::reset_statistics();

    // 参照のポインタ配列 (シャッフル用)
    std::vector<Household*> household_ptrs;
    for(auto& hh : all_households) household_ptrs.push_back(&hh);

    for (int step = 1; step <= total_steps; ++step) {
        if (step % days_permonth == 1) {
            long long current_min_price = PRICE_UNIT;
            std::vector<Firm*> avail;
            for(auto* f : firms_C) if(f->inventory_basic > 0) avail.push_back(f);
            if(!avail.empty()){
                current_min_price = avail[0]->price_basic;
                for(auto* f : avail) if(f->price_basic < current_min_price) current_min_price = f->price_basic;
            }
            for (auto* hh : household_ptrs) hh->update_monthly_budget(current_min_price);
        }

        std::shuffle(household_ptrs.begin(), household_ptrs.end(), gen);

        for (auto* hh : household_ptrs) hh->consume(firms_C, gen);

        if (step % days_permonth == 0) {
            int month = step / days_permonth;
            std::cout << "--- 第" << month << "ヶ月目 処理実行 ---\n";

            for (auto* firm : all_firms) firm->pay_salary();
            for (auto* hh : household_ptrs) hh->pay_tax(&gov, monthly_tax);
            
            if (!firms_G.empty()) {
                long long spending_per_firm = gov_spending / firms_G.size();
                for (auto* firm : firms_G) gov.pay_firm(firm, spending_per_firm);
            }

            long long c_b = Transaction::total_C_basic, c_l = Transaction::total_C_luxury;
            long long total_c = c_b + c_l;
            
            macro_csv << month << "," << c_b << "," << c_l << "," << total_c << "," 
                      << Transaction::total_G << "," << Transaction::total_I << "," 
                      << Transaction::total_T << "," << Transaction::total_S << "," 
                      << (total_c + Transaction::total_G + Transaction::total_I) << "," 
                      << -gov.balance_sheet.assets << "\n";
            Transaction::reset_statistics();

            for (auto* firm : all_firms) {
                firm->calculate_monthly_revenue();
                sales_csv << month << "," << firm->name << "," << firm->monthly_revenue << "," 
                          << firm->inventory_basic << "," << firm->inventory_luxury << "," 
                          << firm->price_basic << "," << firm->price_luxury << "," 
                          << (firm->is_target_G ? "True" : "False") << "\n";
                firm->adjust_prices();
                firm->produce_goods();
            }

            for (auto* hh : household_ptrs) {
                double apc = (hh->monthly_income > 0) ? (double)hh->monthly_consumption_money / hh->monthly_income : 0.0;
                apc_csv << month << "," << hh->name << "," << hh->hierarchy_level << "," 
                        << hh->monthly_income << "," << hh->monthly_consumption_money << "," 
                        << hh->monthly_consumed_vol_basic << "," << apc << "\n";
                hh->previous_income = hh->monthly_income;
                hh->monthly_consumption_money = 0;
                hh->monthly_income = 0;
                hh->monthly_consumed_vol_basic = 0;
            }
        }
    }

    macro_csv.close(); apc_csv.close(); sales_csv.close();

    std::ofstream wealth_csv(d0 + "age01_wealth_distribution_v1.2.csv");
    wealth_csv << "Household_ID,Hierarchy_Level,Final_Assets\n";
    for (const auto& hh : all_households) wealth_csv << hh.name << "," << hh.hierarchy_level << "," << hh.balance_sheet.assets << "\n";
    wealth_csv.close();

    std::cout << "=== シミュレーション完了 ===\n";
    return 0;
}