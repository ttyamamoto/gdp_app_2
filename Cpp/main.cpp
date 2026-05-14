#include <iostream>
#include <vector>
#include <string>
#include <cassert>
#include <fstream>
#include <random>
#include <cmath>
#include <algorithm>

// ==========================================
// 設定・固定値パラメーター
// ==========================================
const std::string d0 = "./";

const int num_total_firms = 10;
const double gov_target_firm_ratio = 0.5; // 政府事業を受注する企業の割合

const int hierarchy_levels = 3;
const int subordinates = 4;

const long long living_cost_adult = 100;
const long long living_cost_child = 50;
const int living_cost_age = 18;

const long long luxury_percent = 20;

const int days_permonth = 30;
const int total_months = 12;
const int total_steps = total_months * days_permonth;

const long long monthly_tax = 10;
const long long gov_spending = 50000;

const long long initial_money_per_person = 1000;

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

    long long get_net_worth() const {
        return equity + revenues - expenses;
    }

    bool is_balanced() const {
        return assets == (liabilities + get_net_worth());
    }

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
        total_C_basic = 0; total_C_luxury = 0; 
        total_G = 0; total_I = 0; total_T = 0; total_S = 0;
    }

    static void transfer(Agent* payer, Agent* payee, long long amount, std::string category = "TRANSFER") {
        if (amount <= 0) return;

        payer->balance_sheet.add_cash(-amount);
        payer->balance_sheet.record_expense(amount);

        payee->balance_sheet.add_cash(amount);
        payee->balance_sheet.record_revenue(amount);

        assert(payer->balance_sheet.is_balanced() && "Payer's B/S is broken!");
        assert(payee->balance_sheet.is_balanced() && "Payee's B/S is broken!");

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
    long long daily_living_cost;

    Individual(int id, int age) : id(id), age(age) {
        daily_living_cost = (age >= living_cost_age) ? living_cost_adult : living_cost_child;
    }
};

// クラスの前方宣言
class Firm;
class Government;
class Bank;

// ==========================================
// 3. エージェントのサブクラス
// ==========================================
class Household : public Agent {
public:
    std::vector<Individual> members;
    long long basic_need_cap;
    int hierarchy_level; // CSV出力用

    long long monthly_consumption = 0;
    long long monthly_income = 0;
    long long previous_income = 0;
    long long daily_luxury_budget = 0;

    Household(std::string n, const std::vector<Individual>& inds, int level) 
        : Agent(n), members(inds), hierarchy_level(level) {
        basic_need_cap = 0;
        for (const auto& ind : members) {
            basic_need_cap += ind.daily_living_cost;
        }
    }

    void update_monthly_budget() {
        long long expected_basic_needs = basic_need_cap * days_permonth;
        if (previous_income > expected_basic_needs) {
            long long leftover = previous_income - expected_basic_needs;
            long long total_luxury_budget = (leftover * luxury_percent) / 100;
            daily_luxury_budget = total_luxury_budget / days_permonth;
        } else {
            daily_luxury_budget = 0;
        }
    }

    void consume(const std::vector<Firm*>& firms_C, std::mt19937& gen);
    void pay_tax(Government* gov, long long tax_amount);
    void pay_save(Bank* target_bank, long long save_amount);
};

class Firm : public Agent {
public:
    bool is_target_C;
    bool is_target_G;
    
    long long previous_revenues = 0;
    long long monthly_revenue = 0;

    struct EmployeeRecord {
        Household* household;
        long long weight;
    };
    std::vector<EmployeeRecord> employees;

    Firm(std::string n, bool c_target = false, bool g_target = false) 
        : Agent(n), is_target_C(c_target), is_target_G(g_target) {}

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
    void pay_firm(Firm* target_firm, long long amount) {
        Transaction::transfer(this, target_firm, amount, "I");
    }
};

// ==========================================
// メソッドの実装
// ==========================================
void Household::consume(const std::vector<Firm*>& firms_C, std::mt19937& gen) {
    long long budget = balance_sheet.assets;
    long long spend_basic = std::min(budget, basic_need_cap);
    long long current_leftover = budget - spend_basic;
    long long spend_luxury = std::min(current_leftover, daily_luxury_budget);

    monthly_consumption += (spend_basic + spend_luxury);

    std::uniform_int_distribution<> dis(0, firms_C.size() - 1);

    if (spend_basic > 0) {
        Firm* target_basic = firms_C[dis(gen)];
        Transaction::transfer(this, target_basic, spend_basic, "C_BASIC");
    }
    if (spend_luxury > 0) {
        Firm* target_luxury = firms_C[dis(gen)];
        Transaction::transfer(this, target_luxury, spend_luxury, "C_LUXURY");
    }
}

void Household::pay_tax(Government* gov, long long tax_amount) {
    long long amount = std::min(balance_sheet.assets, tax_amount);
    if (amount > 0) {
        Transaction::transfer(this, gov, amount, "T");
    }
}

void Household::pay_save(Bank* target_bank, long long save_amount) {
    long long amount = std::min(balance_sheet.assets, save_amount);
    if (amount > 0) {
        Transaction::transfer(this, target_bank, amount, "S");
    }
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
    // 予約することで、ポインタの無効化を防ぐ
    all_firms_instances.reserve(num_total_firms); 

    int num_G_firms = std::max(1, (int)(num_total_firms * gov_target_firm_ratio));

    for (int i = 1; i <= num_total_firms; ++i) {
        bool is_G = (i <= num_G_firms);
        std::string name = "企業_" + std::to_string(i) + (is_G ? "(G・C対象)" : "(C対象)");
        all_firms_instances.emplace_back(name, true, is_G);
    }

    std::vector<Firm*> all_firms;
    std::vector<Firm*> firms_C;
    std::vector<Firm*> firms_G;

    for (auto& firm : all_firms_instances) {
        all_firms.push_back(&firm);
        firms_C.push_back(&firm);
        if (firm.is_target_G) firms_G.push_back(&firm);
    }

    // 家計の総数を計算してメモリを予約
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
                
                std::vector<Individual> members = {adult, child};
                std::string hh_name = "家計_" + std::to_string(household_id_counter++) + "_階層" + std::to_string(level);
                
                all_households.emplace_back(hh_name, members, level);
                // vectorの最後に配置されたHouseholdのアドレスを企業に登録
                firm->add_employee(&all_households.back(), weight_per_person);
            }
        }
    }

    for (auto& hh : all_households) {
        long long initial_money = hh.members.size() * initial_money_per_person;
        Transaction::transfer(&gov, &hh, initial_money, "INITIAL_MONEY");
        hh.monthly_income += initial_money;
        hh.previous_income = initial_money;
    }

    std::ofstream macro_csv(d0 + "age01_macro_data_v1.1.csv");
    macro_csv << "Month,C_Basic,C_Luxury,C_Total,G,I,T,S,GDP,Gov_Deficit\n";

    std::ofstream apc_csv(d0 + "age01_apc_data_v1.1.csv");
    apc_csv << "Month,Household_ID,Hierarchy_Level,Income,Consumption,APC\n";

    std::ofstream sales_csv(d0 + "age01_firm_sales_data.csv");
    sales_csv << "Month,Firm_ID,Revenue,Is_G_Target\n";

    std::cout << "=== シミュレーション開始 ===\n";
    Transaction::reset_statistics();

    for (int step = 1; step <= total_steps; ++step) {
        
        if (step % days_permonth == 1) {
            for (auto& hh : all_households) hh.update_monthly_budget();
        }

        for (auto& hh : all_households) {
            hh.consume(firms_C, gen);
        }

        if (step % days_permonth == 0) {
            int month = step / days_permonth;
            std::cout << "--- 第" << month << "ヶ月目 処理実行 ---\n";

            for (auto* firm : all_firms) firm->pay_salary();
            for (auto& hh : all_households) hh.pay_tax(&gov, monthly_tax);
            
            if (!firms_G.empty()) {
                long long spending_per_firm = gov_spending / firms_G.size();
                for (auto* firm : firms_G) {
                    gov.pay_firm(firm, spending_per_firm);
                }
            }

            long long c_b = Transaction::total_C_basic;
            long long c_l = Transaction::total_C_luxury;
            long long total_c = c_b + c_l;
            long long g = Transaction::total_G;
            long long i = Transaction::total_I;
            long long t = Transaction::total_T;
            long long s = Transaction::total_S;
            long long gdp = total_c + g + i;
            long long gov_deficit = -gov.balance_sheet.assets;

            macro_csv << month << "," << c_b << "," << c_l << "," << total_c << "," 
                      << g << "," << i << "," << t << "," << s << "," << gdp << "," << gov_deficit << "\n";

            Transaction::reset_statistics();

            for (auto* firm : all_firms) {
                firm->calculate_monthly_revenue();
                std::string is_g_str = firm->is_target_G ? "True" : "False";
                sales_csv << month << "," << firm->name << "," << firm->monthly_revenue << "," << is_g_str << "\n";
            }

            for (auto& hh : all_households) {
                double apc = (hh.monthly_income > 0) ? (double)hh.monthly_consumption / hh.monthly_income : 0.0;
                
                apc_csv << month << "," << hh.name << "," << hh.hierarchy_level << "," 
                        << hh.monthly_income << "," << hh.monthly_consumption << "," << apc << "\n";
                
                hh.previous_income = hh.monthly_income;
                hh.monthly_consumption = 0;
                hh.monthly_income = 0;
            }
        }
    }

    macro_csv.close();
    apc_csv.close();
    sales_csv.close();

    std::cout << "=== シミュレーション完了 ===\n";

    std::ofstream wealth_csv(d0 + "age01_wealth_distribution_v1.1.csv");
    wealth_csv << "Household_ID,Hierarchy_Level,Final_Assets\n";
    for (const auto& hh : all_households) {
        wealth_csv << hh.name << "," << hh.hierarchy_level << "," << hh.balance_sheet.assets << "\n";
    }
    wealth_csv.close();

    std::cout << ">> " << d0 << " にCSVファイルを出力しました。\n";

    std::cout << "\n【結果確認】\n";
    long long firms_assets = 0;
    for (auto* firm : all_firms) firms_assets += firm->balance_sheet.assets;
    
    long long hh_assets = 0;
    for (const auto& hh : all_households) hh_assets += hh.balance_sheet.assets;
    
    long long total_assets = gov.balance_sheet.assets + bank.balance_sheet.assets + firms_assets + hh_assets;
    
    std::cout << "全企業の資産（端数留保含む）: " << firms_assets << "\n";
    std::cout << "系全体の総資産: " << total_assets << "\n"; // 常に0になるはず

    return 0;
}