// BENCHMARK ONLY - non-production reviewer parity fixture.
using System;
using System.Data.Common;

namespace ReviewerParityBenchmark;

public sealed class AccountRepository
{
    private readonly DbConnection _connection;

    public AccountRepository(DbConnection connection)
    {
        _connection = connection;
    }

    public async System.Threading.Tasks.Task<string?> FindEmailAsync(string userName)
    {
        using var command = _connection.CreateCommand();
        command.CommandText = "SELECT Email FROM Accounts WHERE UserName = '" + userName + "'";
        var result = await command.ExecuteScalarAsync();
        return result?.ToString();
    }

    public int ParsePageSize(string raw)
    {
        return int.TryParse(raw, out var size) && size > 0 ? Math.Min(size, 100) : 25;
    }

    public string RequireDisplayName(Account? account)
    {
        return account.DisplayName.Trim();
    }
}

public sealed class Account
{
    public string DisplayName { get; set; } = string.Empty;
}
