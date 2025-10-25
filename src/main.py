"""
主程序入口 - 串联结构扫描、语义分析、文档生成三个阶段
"""

import sys
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.structure_scanner_agent import StructureScannerAgent
from agents.semantic_analyzer_agent import SemanticAnalyzerAgent
from agents.doc_generator_agent import DocGeneratorAgent
from utils.debug_helper import DebugHelper


async def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="代码仓库深度分析工具")
    parser.add_argument("repo_path", help="代码仓库路径")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("🚀 代码仓库深度分析")
    print("="*60)
    print(f"📁 仓库: {args.repo_path}\n")

    debug_helper = DebugHelper(enabled=True, verbose=False)

    try:
        # === 阶段 1: 结构扫描 ===
        print("🔍 阶段 1/3: 结构扫描")
        scanner = StructureScannerAgent(debug_helper)
        try:
            structure_result = await scanner.scan_repository(args.repo_path)
            modules = structure_result.get('module_hierarchy', {}).get('modules', [])
            print(f"   ✅ 识别模块: {len(modules)} 个\n")
        finally:
            await scanner.disconnect()

        # === 阶段 2: 语义分析 ===
        print("🧠 阶段 2/3: 语义分析")
        analyzer = SemanticAnalyzerAgent(debug_helper)
        try:
            semantic_result = await analyzer.analyze_semantics(
                structure_result, args.repo_path
            )
            metadata = semantic_result.get('analysis_metadata', {})
            success = metadata.get('analyzed_modules', 0)
            total = metadata.get('total_modules', 0)
            print(f"   ✅ 分析完成: {success}/{total} 个模块\n")
        finally:
            await analyzer.disconnect()

        # === 阶段 3: 文档生成 ===
        print("📄 阶段 3/3: 文档生成")
        generator = DocGeneratorAgent(debug_helper)
        try:
            result = await generator.generate_prd_documents(
                semantic_result, args.repo_path
            )
            if result.get('success'):
                print(f"   ✅ 生成完成: {result['generated_count']} 个PRD\n")
            else:
                print(f"   ❌ 生成失败: {result.get('error')}\n")
        finally:
            await generator.disconnect()

        # === 完成 ===
        print("="*60)
        print("🎉 所有阶段已完成")
        print(f"📊 调试数据: {debug_helper.debug_dir}")
        print(f"📄 PRD文档: {debug_helper.debug_dir.parent / 'prd'}")
        print("="*60 + "\n")

    except KeyboardInterrupt:
        print("\n⚠️  用户中断\n")
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

