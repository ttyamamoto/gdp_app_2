#include <iostream>
#include <vector>
#include <string>
#include <cassert>
#include <fstream>
#include <random>

// ==========================================
// 固定値・パラメータ設定
// ==========================================
const std::string d0 = "./"; // CSV出力先ディレクトリ

const int living_cost_adult = 100;
const int living_cost_child = 50;
const int living_cost_age = 18;

const int total_steps = 360; // 12ヶ月
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
    virtual ~Agent() = default; // ポリモーフィズムのための仮想デストラクタ
};

class Transaction {
public:
    static long long total_C, total_G, total_I, total_T, total_S;

    static void reset_statistics() {
        total_C = 0; total_G = 0; total_I = 0; total_T = 0; total_S = 0;
    }

    static void transfer(Agent* payer, Agent* payee, long long amount, std::string category = "TRANSFER") {
        if (amount <= 0) return;

        payer->balance_sheet.add_cash(-amount);
        payer->balance_sheet.record_expense(amount);

        payee->balance_sheet.add_cash(amount);
        payee->balance_sheet.record_revenue(amount);

        assert(payer->balance_sheet.is_balanced() && "Payer's B/S is broken!");
        assert(payee->balance_sheet.is_balanced() && "Payee's B/S is broken!");

        if (category == "C") total_C += amount;
        else if (category == "G") total_G += amount;
        else if (category == "I") total_I += amount;
        else if (category == "T") total_T += amount;
        else if (category == "S") total_S += amount;
    }
};

// 静的メンバ変数の実体定義
long long Transaction::total_C = 0;
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

// ==========================================
// クラスの前方宣言 (相互参照のため)
// ==========================================
class Firm;
class Government;
class Bank;

// ==========================================
// 3. エージェントのサブクラス
// ==========================================
class Household : public Agent {
public:
    std::vector<Individual> members;
    long long daily_expense_cap;

    Household(std::string n, const std::vector<Individual>& inds) : Agent(n), members(inds) {
        daily_expense_cap = 0;
        for (const auto& ind : members) {
            daily_expense_cap += ind.daily_living_cost;
        }
    }

    void consume(Firm* target_firm);
    void pay_tax(Government* gov, long long tax_amount);
    void pay_save(Bank* target_bank, long long save_amount);
};

class Firm : public Agent {
public:
    bool is_target_C;
    bool is_target_G;
    
    struct EmployeeRecord {
        Household* household;
        double ratio;
    };
    std::vector<EmployeeRecord> employees;

    Firm(std::string n, bool c_target = false, bool g_target = false) 
        : Agent(n), is_target_C(c_target), is_target_G(g_target) {}

    void add_employee(Household* hh, double salary_ratio) {
        employees.push_back({hh, salary_ratio});
    }

    void pay_salary() {
        long long total_payroll = balance_sheet.assets;
        if (total_payroll <= 0) return;

        for (const auto& emp : employees) {
            long long amount = static_cast<long long>(total_payroll * emp.ratio);
            if (amount > 0) {
                Transaction::transfer(this, emp.household, amount, "SALARY");
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
// メソッドの実装 (前方宣言の解決)
// ==========================================
void Household::consume(Firm* target_firm) {
    long long budget = balance_sheet.assets;
    long long actual_spending = std::min(budget, daily_expense_cap);
    if (actual_spending > 0) {
        Transaction::transfer(this, target_firm, actual_spending, "C");
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
    // 乱数生成器の準備
    std::random_device rd;
    std::mt19937 gen(rd());

    // エージェントの生成 (ポインタで管理)
    Government gov("政府");
    Bank bank("銀行");

    Firm firm_G("公共事業(G対象)", false, true);
    std::vector<Firm> firms_C;
    for (int i = 1; i <= 9; ++i) {
        firms_C.emplace_back("消費財メーカー" + std::to_string(i) + "(C対象)", true, false);
    }

    // 全企業をまとめるポインタリスト
    std::vector<Firm*> all_firms;
    all_firms.push_back(&firm_G);
    for (auto& firm : firms_C) {
        all_firms.push_back(&firm);
    }

    std::vector<Household> all_households;

    // 階層構造の設定
    int hierarchy_levels = 3;
    int subordinates = 4;

    int household_id_counter = 1;
    int individual_id_counter = 1;

    for (auto* firm : all_firms) {
        for (int level = 0; level < hierarchy_levels; ++level) {
            int num_people_in_level = std::pow(subordinates, level);
            double ratio_per_person = (1.0 / hierarchy_levels) / num_people_in_level;

            for (int p = 0; p < num_people_in_level; ++p) {
                Individual adult(individual_id_counter++, 30);
                Individual child(individual_id_counter++, 10);
                
                std::vector<Individual> members = {adult, child};
                std::string hh_name = "家計_" + std::to_string(household_id_counter++) + "_階層" + std::to_string(level);
                
                all_households.emplace_back(hh_name, members);
            }
        }
    }

    // emplace_backでベクターを構築し終わってから、アドレスを企業に登録する
    // (ベクターの再確保によるアドレス変更を防ぐため)
    int hh_index = 0;
    for (auto* firm : all_firms) {
        for (int level = 0; level < hierarchy_levels; ++level) {
            int num_people_in_level = std::pow(subordinates, level);
            double ratio_per_person = (1.0 / hierarchy_levels) / num_people_in_level;
            for (int p = 0; p < num_people_in_level; ++p) {
                firm->add_employee(&all_households[hh_index++], ratio_per_person);
            }
        }
    }

    // 初期資産の配布
    for (auto& hh : all_households) {
        long long initial_money = hh.members.size() * initial_money_per_person;
        Transaction::transfer(&gov, &hh, initial_money, "INITIAL_MONEY");
    }

    // CSV用のデータ記録
    std::ofstream macro_csv(d0 + "age01_macro_data.csv");
    macro_csv << "Month,C,G,I,T,S,GDP,Gov_Deficit\n";

    std::cout << "=== シミュレーション開始 ===\n";
    Transaction::reset_statistics();

    std::uniform_int_distribution<> dis(0, firms_C.size() - 1);

    for (int step = 1; step <= total_steps; ++step) {
        // 毎日: 消費
        for (auto& hh : all_households) {
            int random_index = dis(gen);
            hh.consume(&firms_C[random_index]);
        }

        // 30日ごと: 月末処理
        if (step % 30 == 0) {
            int month = step / 30;
            std::cout << "--- 第" << month << "ヶ月目 処理実行 ---\n";

            for (auto* firm : all_firms) firm->pay_salary();
            for (auto& hh : all_households) hh.pay_tax(&gov, monthly_tax);
            gov.pay_firm(&firm_G, gov_spending);

            // データの記録
            long long c = Transaction::total_C;
            long long g = Transaction::total_G;
            long long i = Transaction::total_I;
            long long t = Transaction::total_T;
            long long s = Transaction::total_S;
            long long gdp = c + g + i;
            long long gov_deficit = -gov.balance_sheet.assets;

            macro_csv << month << "," << c << "," << g << "," << i << "," << t << "," 
                      << s << "," << gdp << "," << gov_deficit << "\n";

            Transaction::reset_statistics();
        }
    }
    macro_csv.close();
    std::cout << "=== シミュレーション完了 ===\n";

    // 富の分布CSV出力
    std::ofstream wealth_csv(d0 + "age01_wealth_distribution.csv");
    wealth_csv << "Household_ID,Hierarchy_Level,Final_Assets\n";
    for (const auto& hh : all_households) {
        // 文字列から階層を抽出
        size_t pos = hh.name.find("階層");
        std::string level = (pos != std::string::npos) ? hh.name.substr(pos + 6) : "Unknown";
        wealth_csv << hh.name << "," << level << "," << hh.balance_sheet.assets << "\n";
    }
    wealth_csv.close();
    std::cout << ">> CSVファイルを出力しました。\n\n";

    // 結果確認
    std::cout << "【結果確認】\n";
    std::cout << "政府の最終資産(負債): " << gov.balance_sheet.assets << "\n";
    
    long long firms_assets = firm_G.balance_sheet.assets;
    for (const auto& firm : firms_C) firms_assets += firm.balance_sheet.assets;
    std::cout << "全企業の資産: " << firms_assets << "\n";

    long long hh_assets = 0;
    for (const auto& hh : all_households) hh_assets += hh.balance_sheet.assets;
    std::cout << "全家計の資産: " << hh_assets << "\n";

    long long total_assets = gov.balance_sheet.assets + bank.balance_sheet.assets + firms_assets + hh_assets;
    std::cout << "系全体の総資産: " << total_assets << "\n"; // 常に0になるはず

    return 0;
}