using System.Text.Json;

internal static class StatsText {
    static int[]? Read(JsonElement cat, string key) {
        if (!cat.TryGetProperty(key, out var value) || value.ValueKind != JsonValueKind.Array || value.GetArrayLength() != 7) return null;
        var result = new int[7]; int i = 0;
        foreach (var item in value.EnumerateArray()) {
            if (!item.TryGetInt32(out result[i++])) return null;
        }
        return result;
    }
    internal static int[]? Total(JsonElement cat) {
        var a=Read(cat,"base_stats"); var b=Read(cat,"bonus_stats"); var c=Read(cat,"extra_stats");
        return a==null || b==null || c==null ? null : Enumerable.Range(0,7).Select(i=>a[i]+b[i]+c[i]).ToArray();
    }
    static string Vector(int[]? values) => values==null ? "未记录" : string.Join(" / ",values);
    internal static string Describe(JsonElement cat) =>
        "存档属性合计："+Vector(Total(cat))+Environment.NewLine+
        "  基础："+Vector(Read(cat,"base_stats"))+Environment.NewLine+
        "  成长加成："+Vector(Read(cat,"bonus_stats"))+Environment.NewLine+
        "  额外修正："+Vector(Read(cat,"extra_stats"))+Environment.NewLine+
        "（合计为以上三项之和，不含未记录的装备／战斗临时效果）";
    internal static string Compare(JsonElement start, JsonElement end) {
        var a=Total(start); var b=Total(end);
        if(a==null || b==null) return "开始或结束的属性数据不完整，不能计算差值。";
        var diff=Enumerable.Range(0,7).Select(i=>b[i]-a[i]).Select(n=>n>0?"+"+n:n.ToString());
        return "开始："+Vector(a)+Environment.NewLine+"结束："+Vector(b)+Environment.NewLine+"变化："+string.Join(" / ",diff);
    }
}
